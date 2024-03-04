from contextlib import asynccontextmanager
import secrets
from typing import TYPE_CHECKING, Optional
from pydantic import ValidationError
from streamtasks.client.receiver import Receiver
from streamtasks.client.signal import send_signal
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.types import Message, TopicDataMessage, TopicMessage
from streamtasks.services.protocols import AddressNameAssignmentMessage, GenerateAddressesRequestMessage, GenerateAddressesRequestMessageBase, GenerateAddressesResponseMessage, GenerateAddressesResponseMessageBase, RegisterAddressRequestBody, WorkerAddresses, WorkerRequestDescriptors, WorkerPorts, WorkerTopics
import asyncio
if TYPE_CHECKING:
  from streamtasks.client import Client

class TopicSignalReceiver(Receiver):
  def __init__(self, client: 'Client', topic: int):
    super().__init__(client)
    self._topic = topic
    self._signal_event = asyncio.Event()

  async def _on_start_recv(self): await self._client.register_in_topics([self._topic])
  async def _on_stop_recv(self): await self._client.unregister_in_topics([self._topic])

  async def wait(self):
    async with self:
      await self._signal_event.wait()

  def on_message(self, message: Message):
    if not isinstance(message, TopicMessage): return
    if message.topic != self._topic: return
    self._signal_event.set()


class AddressNameAssignedReceiver(Receiver):
  _recv_queue: asyncio.Queue[AddressNameAssignmentMessage]
  async def _on_start_recv(self): await self._client.register_in_topics([WorkerTopics.ADDRESS_NAME_ASSIGNED])
  async def _on_stop_recv(self): await self._client.unregister_in_topics([WorkerTopics.ADDRESS_NAME_ASSIGNED])
  def on_message(self, message: Message):
    if not isinstance(message, TopicDataMessage): return
    if message.topic != WorkerTopics.ADDRESS_NAME_ASSIGNED: return
    if not isinstance(message.data, MessagePackData): return
    try:
      self._recv_queue.put_nowait(AddressNameAssignmentMessage.model_validate(message.data.data))
    except ValidationError: pass

class ResolveAddressesReceiver(Receiver):
  def __init__(self, client: 'Client', request_id: int):
    super().__init__(client)
    self._request_id = request_id
    self._recv_queue: asyncio.Queue[GenerateAddressesResponseMessage]

  async def _on_start_recv(self): await self._client.register_in_topics([WorkerTopics.ADDRESSES_CREATED])
  async def _on_stop_recv(self): await self._client.unregister_in_topics([WorkerTopics.ADDRESSES_CREATED])

  def on_message(self, message: Message):
    if isinstance(message, TopicDataMessage) and message.topic == WorkerTopics.ADDRESSES_CREATED:
      sd_message: TopicDataMessage = message
      if isinstance(sd_message.data, MessagePackData):
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
        WorkerAddresses.ID_DISCOVERY,
        WorkerRequestDescriptors.REQUEST_ADDRESSES,
        GenerateAddressesRequestMessage(request_id=request_id, count=count).model_dump()
      )
      data: GenerateAddressesResponseMessage = await receiver.recv()
  else: 
    res = await client.fetch(WorkerAddresses.ID_DISCOVERY, WorkerRequestDescriptors.REQUEST_ADDRESSES, GenerateAddressesRequestMessageBase(count=count).model_dump())
    data = GenerateAddressesResponseMessageBase.model_validate(res)
  addresses = set(data.addresses)
  if len(addresses) != count: raise Exception("The response returned an invalid number of addresses")
  return addresses

async def _register_address_name(client: 'Client', name: str, address: Optional[int]):
  await client.fetch(WorkerAddresses.ID_DISCOVERY, WorkerRequestDescriptors.REGISTER_ADDRESS, RegisterAddressRequestBody(address_name=name, address=address).model_dump())
  client.set_address_name(name, address)

async def register_address_name(client: 'Client', name: str, address: int): return await _register_address_name(client, name, address)

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
      data = await receiver.recv()
      client.set_address_name(data.address_name, data.address)
      if data.address_name == name: found_address = data.address
  while not receiver.empty():
    data: AddressNameAssignmentMessage = await receiver.get()
    client.set_address_name(data.address_name, data.address)
  return found_address
