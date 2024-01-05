from abc import ABC, abstractmethod
import asyncio

from pydantic import ValidationError
from streamtasks.message.data import MessagePackData, SerializableData
from streamtasks.net.types import AddressedMessage, Message, TopicControlData, TopicControlMessage, TopicDataMessage, TopicMessage
from typing import Iterable, Optional, Any, TYPE_CHECKING

from streamtasks.system.protocols import AddressNameAssignmentMessage, GenerateAddressesResponseMessage, WorkerTopics

if TYPE_CHECKING:
  from streamtasks.client import Client


class Receiver(ABC):
  _client: 'Client'
  _receiving_count: int

  def __init__(self, client: 'Client'):
    self._recv_queue = asyncio.Queue()
    self._client = client
    self._receiving_count = 0

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

  async def get(self) -> Any: return await self._recv_queue.get()
  async def recv(self) -> Any:
    async with self:
      return await self._recv_queue.get()


class AddressReceiver(Receiver):
  def __init__(self, client: 'Client', address: int, port: int):
    super().__init__(client)
    self._address = address
    self._port = port

  def on_message(self, message: Message):
    if not isinstance(message, AddressedMessage): return
    a_message: AddressedMessage = message
    if a_message.address == self._address and a_message.port == self._port:
      self._recv_queue.put_nowait((a_message.address, a_message.data))


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


class TopicsReceiver(Receiver):
  _topics: set[int]
  _control_data: dict[int, TopicControlData]
  _recv_queue: asyncio.Queue[tuple[int, Optional[SerializableData], Optional[TopicControlData]]]

  def __init__(self, client: 'Client', topics: Iterable[int], subscribe: bool = True):
    super().__init__(client)
    self._topics = set(topics)
    self._control_data = {}
    self._subscribe = subscribe

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
  _recv_queue: asyncio.Queue[GenerateAddressesResponseMessage]
  _request_id: int

  def __init__(self, client: 'Client', request_id: int):
    super().__init__(client)
    self._request_id = request_id

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