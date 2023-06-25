from typing import Union, Optional, Any, Callable, Awaitable
from abc import ABC, abstractmethod
from dataclasses import dataclass
import asyncio
from streamtasks.comm import *
from streamtasks.protocols import *
from streamtasks.comm.serialization import *
import weakref
import secrets

class Receiver(ABC):
  _client: 'Client'
  _receiving_count: int

  def __init__(self, client: 'Client'):
    self._recv_queue = asyncio.Queue()
    self._client = client
    self._receiving_count = 0
  
  def start_recv(self):
    self._receiving_count += 1 
    if self._receiving_count > 1: return
    self._client.enable_receiver(self)

  def stop_recv(self): 
    self._receiving_count = max(0, self._receiving_count - 1)
    if self._receiving_count > 0: return
    self._client.disable_receiver(self)

  def __enter__(self):
    self.start_recv()
    return self
  def __exit__(self, *args):
    self.stop_recv()
    return False

  @abstractmethod
  def on_message(self, message: Message):
    pass

  def empty(self): return self._recv_queue.empty()

  async def recv(self) -> Any:
    with self:
      return await self._recv_queue.get()

class AddressReceiver(Receiver):
  _addresses: set[int]

  def __init__(self, client: 'Client', addresses: set[int]):
    super().__init__(client)
    self._addresses = addresses

  def on_message(self, message: Message):
    if isinstance(message, AddressedMessage) and message.address in self._addresses:
      a_message: AddressedMessage = message
      self._recv_queue.put_nowait((a_message.address, a_message.data))

class TopicsReceiver(Receiver):
  _topics: set[int]
  _control_data: dict[int, TopicControlData]
  _recv_queue: asyncio.Queue[tuple[int, Optional[Any], Optional[TopicControlData]]]

  def __init__(self, client: 'Client', topics: set[int]):
    super().__init__(client)
    self._topics = topics
    self._control_data = {}
    
  def get_control_data(self, topic: int): return self._control_data.get(topic, None)

  def on_message(self, message: Message):
    if isinstance(message, TopicDataMessage) and message.topic in self._topics:
      sd_message: TopicDataMessage = message
      if sd_message.topic in self._topics:
        self._recv_queue.put_nowait((sd_message.topic, sd_message.data, None))
    elif isinstance(message, TopicControlMessage):
      sc_message: TopicControlMessage = message
      if sc_message.topic in self._topics:
        self._control_data[sc_message.topic] = control_data = sc_message.to_data()
        self._recv_queue.put_nowait((sc_message.topic, None, control_data))

class ResolveAddressesReceiver(Receiver):
  _recv_queue: asyncio.Queue[ResolveAddressesMessage]
  _request_id: int

  def __init__(self, client: 'Client', request_id: int):
    super().__init__(client)
    self._request_id = request_id

  def on_message(self, message: Message):
    if isinstance(message, TopicDataMessage) and message.topic == WorkerTopics.ADDRESSES_CREATED:
      sd_message: TopicDataMessage = message
      if isinstance(sd_message.data, JsonData):
        try:
          ra_message = ResolveAddressesMessage.parse_obj(sd_message.data.data)
          if ra_message.request_id == self._request_id:
            self._recv_queue.put_nowait(ra_message)
        except: pass