from abc import ABC, abstractmethod
from dataclasses import dataclass
import asyncio
from streamtasks.comm import *
from streamtasks.system.protocols import *
from streamtasks.message.data import *
import weakref
import secrets
import itertools
from typing import Union, Optional, Any, Callable, Awaitable
from streamtasks.client.helpers import SubscribeTracker


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
    self._client.enable_receiver(self)
    await self._on_start_recv()

  async def stop_recv(self): 
    self._receiving_count = max(0, self._receiving_count - 1)
    if self._receiving_count > 0: return
    self._client.disable_receiver(self)
    await self._on_stop_recv()

  async def __aenter__(self): 
    await self.start_recv()
    return self
  async def __aexit__(self, *args): await self.stop_recv()

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

class NoopReceiver(Receiver):
  def __init__(self, client: 'Client'):
    super().__init__(client)
    self._recv_queue = None
  def on_message(self, message: Message): pass
  def empty(self): return True
  async def get(self): raise NotImplementedError("A noop receiver will never receive any messages")
  async def recv(self): raise NotImplementedError("A noop receiver will never receive any messages")

class AddressReceiver(Receiver):
  _addresses: set[int]

  def __init__(self, client: 'Client', addresses: set[int]):
    super().__init__(client)
    self._addresses = addresses

  def on_message(self, message: Message):
    if isinstance(message, AddressedMessage) and message.address in self._addresses:
      a_message: AddressedMessage = message
      self._recv_queue.put_nowait((a_message.address, a_message.data))

class TopicSignalReceiver(Receiver):
  def __init__(self, client: 'Client', topic: int):
    super().__init__(client)
    self._topic = topic
    self._signal_event = asyncio.Event()

  async def _on_start_recv(self): await self._client.subscribe([self._topic])
  async def _on_stop_recv(self): await self._client.unsubscribe([self._topic]) 

  async def wait(self): 
    async with self:
      await self._signal_event.wait()

  def on_message(self, message: Message):
    if not isinstance(message, TopicMessage): return
    if message.topic != self._topic: return
    self._signal_event.set()

class AddressNameAssignedReceiver(Receiver):
  _recv_queue: asyncio.Queue[AddressNameAssignmentMessage]
  async def _on_start_recv(self): await self._client.subscribe([WorkerTopics.ADDRESS_NAME_ASSIGNED])
  async def _on_stop_recv(self): await self._client.unsubscribe([WorkerTopics.ADDRESS_NAME_ASSIGNED])
  def on_message(self, message: Message):
    if not isinstance(message, TopicDataMessage): return
    if message.topic != WorkerTopics.ADDRESS_NAME_ASSIGNED: return
    if not isinstance(message.data, MessagePackData): return
    try:
      self._recv_queue.put_nowait(AddressNameAssignmentMessage.parse_obj(message.data.data))
    except: pass

class TopicsReceiver(Receiver):
  _topics: set[int]
  _control_data: dict[int, TopicControlData]
  _recv_queue: asyncio.Queue[tuple[int, Optional[Any], Optional[TopicControlData]]]

  def __init__(self, client: 'Client', topics: Iterable[Union[int, 'SubscribeTracker']], subscribe: bool = True):
    super().__init__(client)
    self._topics = set(t for t in topics if isinstance(t, int))
    self._tracked_topics = [ t for t in topics if isinstance(t, SubscribeTracker) ]
    self._control_data = {}
    self._subscribe = subscribe
    
  def get_control_data(self, topic: int): return self._control_data.get(topic, None)

  async def _on_start_recv(self): 
    if self._subscribe and len(self._topics) > 0: await self._client.subscribe(self._topics)
  async def _on_stop_recv(self): 
    if self._subscribe and len(self._topics) > 0: await self._client.unsubscribe(self._topics)

  def on_message(self, message: Message):
    topics = itertools.chain(self._topics, (t.topic for t in self._tracked_topics))
    if isinstance(message, TopicMessage) and message.topic in topics:
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

  async def _on_start_recv(self): await self._client.subscribe([WorkerTopics.ADDRESSES_CREATED])
  async def _on_stop_recv(self): await self._client.unsubscribe([WorkerTopics.ADDRESSES_CREATED])

  def on_message(self, message: Message):
    if isinstance(message, TopicDataMessage) and message.topic == WorkerTopics.ADDRESSES_CREATED:
      sd_message: TopicDataMessage = message
      if isinstance(sd_message.data, JsonData):
        try:
          ra_message = GenerateAddressesResponseMessage.parse_obj(sd_message.data.data)
          if ra_message.request_id == self._request_id:
            self._recv_queue.put_nowait(ra_message)
        except: pass