from typing import Optional
from pydantic import ValidationError
from streamtasks.client import Client
from streamtasks.client.receiver import Receiver
from streamtasks.message.data import MessagePackData
from streamtasks.net.types import Message, TopicDataMessage, TopicMessage
from streamtasks.services.protocols import AddressNameAssignmentMessage, RegisterAddressRequestBody, WorkerAddresses, WorkerFetchDescriptors, WorkerTopics
import asyncio


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


async def _register_address_name(client: Client, name: str, address: Optional[int]):
  await client.fetch(WorkerAddresses.ID_DISCOVERY, WorkerFetchDescriptors.REGISTER_ADDRESS, RegisterAddressRequestBody(address_name=name, address=address).model_dump())
  client.set_address_name(name, address)


async def register_address_name(client: Client, name: str, address: int): return await _register_address_name(client, name, address)


async def unregister_address_name(client: Client, name: str): return await _register_address_name(client, name, None)


async def wait_for_topic_signal(client: Client, topic: int): return await TopicSignalReceiver(client, topic).wait()


async def wait_for_address_name(client: Client, name: str):
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
