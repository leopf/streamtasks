from abc import ABC, abstractmethod
from streamtasks.net.serialization import RawData
from streamtasks.net.messages import Message, TopicControlData, TopicControlMessage, TopicDataMessage, TopicMessage
from typing import Generic, Iterable, TYPE_CHECKING, TypeVar
import asyncio

if TYPE_CHECKING:
  from streamtasks.client import Client

T = TypeVar("T")

class Receiver(ABC, Generic[T]):
  def __init__(self, client: 'Client'):
    self._recv_queue: asyncio.Queue[T] = asyncio.Queue()
    self._client: 'Client' = client
    self._receiving_count: int = 0

  @abstractmethod
  def on_message(self, message: Message):
    pass

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

  def empty(self): return self._recv_queue.empty()
  async def get(self): return await self._recv_queue.get()
  async def recv(self):
    async with self: return await self.get()

  async def _on_start_recv(self): pass
  async def _on_stop_recv(self): pass

  async def __aenter__(self):
    await self.start_recv()
    return self
  async def __aexit__(self, *_): await self.stop_recv()

class TopicsReceiver(Receiver[tuple[int, RawData | TopicControlData]]):
  def __init__(self, client: 'Client', topics: Iterable[int], subscribe: bool = True):
    super().__init__(client)
    self._topics: set[int] = set(topics)
    self._subscribe = subscribe

  async def _on_start_recv(self):
    if self._subscribe and len(self._topics) > 0: await self._client.register_in_topics(self._topics)
  async def _on_stop_recv(self):
    if self._subscribe and len(self._topics) > 0: await self._client.unregister_in_topics(self._topics)

  def on_message(self, message: Message):
    if isinstance(message, TopicMessage) and message.topic in self._topics:
      if isinstance(message, TopicDataMessage): self._recv_queue.put_nowait((message.topic, message.data))
      elif isinstance(message, TopicControlMessage): self._recv_queue.put_nowait((message.topic, message.to_data()))
