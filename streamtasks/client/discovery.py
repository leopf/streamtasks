from contextlib import asynccontextmanager
import secrets
from typing import TYPE_CHECKING, Optional
from pydantic import BaseModel, ValidationError, field_validator
from streamtasks.client.receiver import Receiver
from streamtasks.client.signal import send_signal
from streamtasks.net.serialization import RawData
from streamtasks.net.messages import Message, TopicDataMessage, TopicMessage
from streamtasks.net.utils import validate_address_name
from streamtasks.services.constants import NetworkAddresses, NetworkTopics
import asyncio

if TYPE_CHECKING:
  from streamtasks.client import Client


class DsicoveryConstants:
  REQUEST_TOPICS = "request_topics"

  REQUEST_ADDRESSES = "request_addresses"

  RESOLVE_ADDRESS = "resolve_address_name"
  REGISTER_ADDRESS = "register_address_name"

  REGISTER_TOPIC_SPACE = "register_topic_space"
  GET_TOPIC_SPACE = "get_topic_space"
  GET_TOPIC_SPACE_TRANSLATION = "get_topic_space_translation"
  DELETE_TOPIC_SPACE = "delete_topic_space"


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


class RegisterAddressRequestBody(BaseModel):
  address_name: str
  address: Optional[int] = None

  @field_validator("address_name")
  @classmethod
  def validate_address_name(cls, value: str):
    validate_address_name(value)
    return value


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

class AddressNameAssignedReceiver(Receiver[AddressNameAssignmentMessage]):
  async def _on_start_recv(self): await self._client.register_in_topics([NetworkTopics.ADDRESS_NAME_ASSIGNED])
  async def _on_stop_recv(self): await self._client.unregister_in_topics([NetworkTopics.ADDRESS_NAME_ASSIGNED])
  def on_message(self, message: Message):
    if not isinstance(message, TopicDataMessage): return
    if message.topic != NetworkTopics.ADDRESS_NAME_ASSIGNED: return
    if not isinstance(message.data, RawData): return
    try: self._recv_queue.put_nowait(AddressNameAssignmentMessage.model_validate(message.data.data))
    except ValidationError: pass

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
        DsicoveryConstants.REQUEST_ADDRESSES,
        GenerateAddressesRequestMessage(request_id=request_id, count=count).model_dump()
      )
      data: GenerateAddressesResponseMessage = await receiver.get()
  else:
    res = await client.fetch(NetworkAddresses.ID_DISCOVERY, DsicoveryConstants.REQUEST_ADDRESSES, GenerateAddressesRequestMessageBase(count=count).model_dump())
    data = GenerateAddressesResponseMessageBase.model_validate(res)
  addresses = set(data.addresses)
  if len(addresses) != count: raise Exception("The response returned an invalid number of addresses")
  return addresses

async def delete_topic_space(client: 'Client', id: int): await client.fetch(NetworkAddresses.ID_DISCOVERY, DsicoveryConstants.DELETE_TOPIC_SPACE, TopicSpaceRequestMessage(id=id).model_dump())
async def register_topic_space(client: 'Client', topic_ids: set[int]) -> tuple[int, dict[int, int]]:
  result = await client.fetch(NetworkAddresses.ID_DISCOVERY, DsicoveryConstants.REGISTER_TOPIC_SPACE, RegisterTopicSpaceRequestMessage(topic_ids=topic_ids).model_dump())
  data = TopicSpaceResponseMessage.model_validate(result)
  return (data.id, { k: v for k, v in data.topic_id_map })
async def get_topic_space(client: 'Client', id: int):
  result = await client.fetch(NetworkAddresses.ID_DISCOVERY, DsicoveryConstants.GET_TOPIC_SPACE, TopicSpaceRequestMessage(id=id).model_dump())
  data = TopicSpaceResponseMessage.model_validate(result)
  return { k: v for k, v in data.topic_id_map }
async def get_topic_space_translation(client: 'Client', topic_space_id: int, topic_id: int):
  message = TopicSpaceTranslationRequestMessage(topic_space_id=topic_space_id, topic_id=topic_id)
  result = await client.fetch(NetworkAddresses.ID_DISCOVERY, DsicoveryConstants.GET_TOPIC_SPACE_TRANSLATION, message.model_dump())
  return TopicSpaceTranslationResponseMessage.model_validate(result).topic_id

async def _register_address_name(client: 'Client', name: str, address: Optional[int]):
  await client.fetch(NetworkAddresses.ID_DISCOVERY, DsicoveryConstants.REGISTER_ADDRESS, RegisterAddressRequestBody(address_name=name, address=address).model_dump())
  client.set_address_name(name, address)

async def register_address_name(client: 'Client', name: str, address: int | None = None):
  if address is None and client.address is None: raise ValueError("Missing address! You must either provide and address or the client must have one assigned!")
  return await _register_address_name(client, name, address or client.address)

async def unregister_address_name(client: 'Client', name: str): return await _register_address_name(client, name, None)

@asynccontextmanager
async def address_name_context(client: 'Client', name: str, address: int):
  try:
    await register_address_name(client, name, address)
    yield None
  finally:
    await unregister_address_name(client, name)

async def wait_for_topic_signal(client: 'Client', topic: int): return await TopicSignalReceiver(client, topic).wait()

async def wait_for_address_name(client: 'Client', name: str):
  found_address = client._address_resolver_cache.get(name, None)
  if found_address is not None: return found_address
  receiver = AddressNameAssignedReceiver(client)
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
