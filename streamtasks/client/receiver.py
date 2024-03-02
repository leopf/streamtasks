from abc import ABC, abstractmethod
from pydantic import ValidationError
from streamtasks.net.message.data import MessagePackData, SerializableData
from streamtasks.net.message.types import AddressedMessage, Message, TopicControlData, TopicControlMessage, TopicDataMessage, TopicMessage
from typing import Iterable, Optional, TYPE_CHECKING
from streamtasks.services.protocols import GenerateAddressesResponseMessage, WorkerTopics
import asyncio

if TYPE_CHECKING:
  from streamtasks.client import Client


class Receiver(ABC):
  def __init__(self, client: 'Client'):
    self._recv_queue = asyncio.Queue()
    self._client: 'Client' = client
    self._receiving_count: int = 0

  async def start_recv(self):
    self._receiving_count += 1
    if self._receiving_count > 1: return
    await self._client.enable_receiver(self)
    await asyncio.sleep(0)
    await self._on_start_recv()

  async def stop_recv(self):
    self._receiving_count = max(0, self._receiving_count - 1)
    if self._receiving_count > 0: return
    await self._client.disable_receiver(self)
    await asyncio.sleep(0)
    await self._on_stop_recv()

  async def __aenter__(self):
    await self.start_recv()
    return self
  async def __aexit__(self, *_): await self.stop_recv()

  @abstractmethod
  def on_message(self, message: Message):
    pass

  def empty(self): return self._recv_queue.empty()

  async def _on_start_recv(self): pass
  async def _on_stop_recv(self): pass

  async def get(self): return await self._recv_queue.get()
  async def recv(self):
    async with self:
      return await self._recv_queue.get()


class AddressReceiver(Receiver):
  def __init__(self, client: 'Client', address: int, port: int):
    super().__init__(client)
    self._recv_queue: asyncio.Queue[tuple[int, SerializableData]]
    self._address = address
    self._port = port

  def on_message(self, message: Message):
    if not isinstance(message, AddressedMessage): return
    a_message: AddressedMessage = message
    if a_message.address == self._address and a_message.port == self._port:
      self._recv_queue.put_nowait((a_message.address, a_message.data))


class TopicsReceiver(Receiver):
  def __init__(self, client: 'Client', topics: Iterable[int], subscribe: bool = True):
    super().__init__(client)
    self._topics: set[int] = set(topics)
    self._control_data: dict[int, TopicControlData] = {}
    self._subscribe = subscribe
    self._recv_queue: asyncio.Queue[tuple[int, Optional[SerializableData], Optional[TopicControlData]]]

  def get_control_data(self, topic: int): return self._control_data.get(topic, None)

  async def _on_start_recv(self):
    if self._subscribe and len(self._topics) > 0: await self._client.register_in_topics(self._topics)
  async def _on_stop_recv(self):
    if self._subscribe and len(self._topics) > 0: await self._client.unregister_in_topics(self._topics)

  def on_message(self, message: Message):
    if isinstance(message, TopicMessage) and message.topic in self._topics:
      if isinstance(message, TopicDataMessage):
        sd_message: TopicDataMessage = message
        self._recv_queue.put_nowait((sd_message.topic, sd_message.data, None))
      elif isinstance(message, TopicControlMessage):
        sc_message: TopicControlMessage = message
        self._control_data[sc_message.topic] = control_data = sc_message.to_data()
        self._recv_queue.put_nowait((sc_message.topic, None, control_data))


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