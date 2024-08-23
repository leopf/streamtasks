from contextlib import asynccontextmanager
import secrets
from typing import TYPE_CHECKING, Optional
from pydantic import BaseModel, ValidationError, field_validator
from streamtasks.client.broadcast import BroadcastReceiver
from streamtasks.client.receiver import Receiver
from streamtasks.client.signal import send_signal
from streamtasks.net.serialization import RawData
from streamtasks.net.messages import Message, TopicDataMessage, TopicMessage
from streamtasks.net.utils import validate_address_name
from streamtasks.services.constants import NetworkAddresses, NetworkTopics
import asyncio

if TYPE_CHECKING:
  from streamtasks.client import Client


class DiscoveryConstants:
  FD_REQUEST_TOPICS = "request_topics"
  FD_RESOLVE_ADDRESS = "resolve_address_name"
  FD_REGISTER_ADDRESS_NAME = "register_address_name"
  FD_REGISTER_TOPIC_SPACE = "register_topic_space"
  FD_GET_TOPIC_SPACE = "get_topic_space"
  FD_GET_TOPIC_SPACE_TRANSLATION = "get_topic_space_translation"
  FD_DELETE_TOPIC_SPACE = "delete_topic_space"

  FD_SD_REQUEST_ADDRESSES = "request_addresses"
  SD_UNREGISTER_ADDRESS_NAME = "unregister_address_name"

  BC_ADDRESS_NAME_REGISTERED = "address-name/registered"


class TopicSpaceRequestMessage(BaseModel):
  id: int

class TopicSpaceTranslationRequestMessage(BaseModel):
  topic_space_id: int
  topic_id: int

class RegisterTopicSpaceRequestMessage(BaseModel):
  topic_ids: list[int]

class TopicSpaceTranslationResponseMessage(BaseModel):
  topic_id: int

class TopicSpaceResponseMessage(BaseModel):
  id: int
  topic_id_map: list[tuple[int, int]]

class GenerateAddressesRequestMessageBase(BaseModel):
  count: int

class GenerateAddressesRequestMessage(GenerateAddressesRequestMessageBase):
  request_id: int

class GenerateAddressesResponseMessageBase(BaseModel):
  addresses: list[int]

class GenerateAddressesResponseMessage(GenerateAddressesResponseMessageBase):
  request_id: int

class GenerateTopicsRequestBody(BaseModel):
  count: int


class GenerateTopicsResponseBody(BaseModel):
  topics: list[int]


class ResolveAddressRequestBody(BaseModel):
  address_name: str


class ResolveAddressResonseBody(BaseModel):
  address: Optional[int] = None

class UnregisterAddressNameMessage(BaseModel):
  address_name: str

  @field_validator("address_name")
  @classmethod
  def validate_address_name(cls, value: str):
    validate_address_name(value)
    return value

class RegisterAddressNameRequestBody(UnregisterAddressNameMessage):
  address: int

class AddressNameAssignmentMessage(BaseModel):
  address_name: str
  address: Optional[int] = None

class TopicSignalReceiver(Receiver):
  def __init__(self, client: 'Client', topic: int):
    super().__init__(client)
    self._topic = topic
    self._signal_event = asyncio.Event()

  async def _on_start_recv(self): await self._client.register_in_topics([self._topic])
  async def _on_stop_recv(self): await self._client.unregister_in_topics([self._topic])

  async def wait(self):
    async with self: await self._signal_event.wait()

  def on_message(self, message: Message):
    if isinstance(message, TopicMessage) and message.topic == self._topic: self._signal_event.set()

class AddressNameRegisteredReceiver(BroadcastReceiver[AddressNameAssignmentMessage]):
  def transform_data(self, _: str, data: RawData) -> AddressNameAssignmentMessage: return AddressNameAssignmentMessage.model_validate(data.data)

class ResolveAddressesReceiver(Receiver[GenerateAddressesResponseMessage]):
  def __init__(self, client: 'Client', request_id: int):
    super().__init__(client)
    self._request_id = request_id

  async def _on_start_recv(self): await self._client.register_in_topics([NetworkTopics.ADDRESSES_CREATED])
  async def _on_stop_recv(self): await self._client.unregister_in_topics([NetworkTopics.ADDRESSES_CREATED])

  def on_message(self, message: Message):
    if isinstance(message, TopicDataMessage) and message.topic == NetworkTopics.ADDRESSES_CREATED:
      sd_message: TopicDataMessage = message
      if isinstance(sd_message.data, RawData):
        try:
          ra_message = GenerateAddressesResponseMessage.model_validate(sd_message.data.data)
          if ra_message.request_id == self._request_id:
            self._recv_queue.put_nowait(ra_message)
        except ValidationError: pass

async def request_addresses(client: 'Client', count: int) -> set[int]:
  data: GenerateAddressesResponseMessageBase
  if client.address is None:
    request_id = secrets.randbelow(1 << 64)
    async with ResolveAddressesReceiver(client, request_id) as receiver:
      await send_signal(
        client,
        NetworkAddresses.ID_DISCOVERY,
        DiscoveryConstants.FD_SD_REQUEST_ADDRESSES,
        GenerateAddressesRequestMessage(request_id=request_id, count=count).model_dump()
      )
      data: GenerateAddressesResponseMessage = await receiver.get()
  else:
    res = await client.fetch(NetworkAddresses.ID_DISCOVERY, DiscoveryConstants.FD_SD_REQUEST_ADDRESSES, GenerateAddressesRequestMessageBase(count=count).model_dump())
    data = GenerateAddressesResponseMessageBase.model_validate(res)
  addresses = set(data.addresses)
  if len(addresses) != count: raise Exception("The response returned an invalid number of addresses")
  return addresses

async def delete_topic_space(client: 'Client', id: int): await client.fetch(NetworkAddresses.ID_DISCOVERY, DiscoveryConstants.FD_DELETE_TOPIC_SPACE, TopicSpaceRequestMessage(id=id).model_dump())
async def register_topic_space(client: 'Client', topic_ids: set[int]) -> tuple[int, dict[int, int]]:
  result = await client.fetch(NetworkAddresses.ID_DISCOVERY, DiscoveryConstants.FD_REGISTER_TOPIC_SPACE, RegisterTopicSpaceRequestMessage(topic_ids=topic_ids).model_dump())
  data = TopicSpaceResponseMessage.model_validate(result)
  return (data.id, { k: v for k, v in data.topic_id_map })
async def get_topic_space(client: 'Client', id: int):
  result = await client.fetch(NetworkAddresses.ID_DISCOVERY, DiscoveryConstants.FD_GET_TOPIC_SPACE, TopicSpaceRequestMessage(id=id).model_dump())
  data = TopicSpaceResponseMessage.model_validate(result)
  return { k: v for k, v in data.topic_id_map }
async def get_topic_space_translation(client: 'Client', topic_space_id: int, topic_id: int):
  message = TopicSpaceTranslationRequestMessage(topic_space_id=topic_space_id, topic_id=topic_id)
  result = await client.fetch(NetworkAddresses.ID_DISCOVERY, DiscoveryConstants.FD_GET_TOPIC_SPACE_TRANSLATION, message.model_dump())
  return TopicSpaceTranslationResponseMessage.model_validate(result).topic_id

@asynccontextmanager
async def address_name_context(client: 'Client', name: str, address: int | None = None):
  address = address or client.address
  if address is None: raise ValueError("Missing address!")
  try:
    await client.fetch(NetworkAddresses.ID_DISCOVERY, DiscoveryConstants.FD_REGISTER_ADDRESS_NAME, RegisterAddressNameRequestBody(address_name=name, address=address).model_dump())
    client.set_address_name(name, address)
    yield
  finally:
    await send_signal(client, NetworkAddresses.ID_DISCOVERY, DiscoveryConstants.SD_UNREGISTER_ADDRESS_NAME, UnregisterAddressNameMessage(address_name=name).model_dump())
    client.set_address_name(name, address)

async def wait_for_topic_signal(client: 'Client', topic: int): return await TopicSignalReceiver(client, topic).wait()

async def wait_for_address_name(client: 'Client', name: str):
  found_address = client._address_resolver_cache.get(name, None)
  if found_address is not None: return found_address
  receiver = AddressNameRegisteredReceiver(client, [ DiscoveryConstants.BC_ADDRESS_NAME_REGISTERED ], NetworkAddresses.ID_DISCOVERY)
  async with receiver:
    found_address = await client.resolve_address_name(name)
    while found_address is None:
      data = await receiver.get()
      client.set_address_name(data.address_name, data.address)
      if data.address_name == name: found_address = data.address
  while not receiver.empty():
    data: AddressNameAssignmentMessage = await receiver.get()
    client.set_address_name(data.address_name, data.address)
  return found_address
