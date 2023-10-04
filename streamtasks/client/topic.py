from abc import abstractmethod
import asyncio
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Iterable, Optional
from streamtasks.client.receiver import Receiver
from streamtasks.helpers import AsyncBool
from streamtasks.message.data import SerializableData
from streamtasks.net import Message
from streamtasks.net.types import InTopicsChangedMessage, OutTopicsChangedMessage, TopicControlData, TopicControlMessage, TopicDataMessage

if TYPE_CHECKING:
  from streamtasks.client import Client

class _TopicRegisterContext:
  def __init__(self, topic_obj: '_TopicBase') -> None: self._topic_obj = topic_obj
  async def __aenter__(self): await self._topic_obj.set_registered(True)
  async def __aexit__(self, *_): await self._topic_obj.set_registered(False)

class _TopicBase:
  def __init__(self, client: 'Client', topic: int, registered: bool = False) -> None:
    self._client = client
    self._topic = topic
    self._registered = registered

  @property
  def is_registered(self): return self._registered
  @property
  def topic(self): return self._topic

  def RegisterContext(self): return _TopicRegisterContext(self)

  @abstractmethod
  async def start(self): pass
  @abstractmethod
  async def stop(self): pass
  async def set_registered(self, registered: bool):
    if self._registered == registered: return
    await self._set_registered(registered)
    self._registered = registered

  @abstractmethod
  async def _set_registered(self, registered: bool): pass

  async def __aenter__(self): 
    await self.start()
    return self
  async def __aexit__(self, *_): await self.stop()

class _InTopicAction(Enum):
  SET_COST = auto()
  SET_CONTROL = auto()
  DATA = auto()

class _InTopicReceiver(Receiver):
  _recv_queue: asyncio.Queue[(_InTopicAction, Any)]

  def __init__(self, client: 'Client', topic: int):
    super().__init__(client)
    self._topic = topic

  def _put_msg(self, action: _InTopicAction, data: Any):
    self._recv_queue.put_nowait((action, data))

  def on_message(self, message: Message):
    if isinstance(message, OutTopicsChangedMessage):
      if self._topic in message.remove: self._put_msg(_InTopicAction.SET_COST, None)
      else:
        topic_price_map = { pid.id: pid.cost for pid in message.add }
        if self._topic in topic_price_map: self._put_msg(_InTopicAction.SET_COST, topic_price_map[self._topic])

    if isinstance(message, TopicControlMessage) and message.topic == self._topic:
      self._put_msg(_InTopicAction.SET_CONTROL, message.to_data())

    if isinstance(message, TopicDataMessage) and message.topic == self._topic:
      self._put_msg(_InTopicAction.DATA, message.data)


class InTopic(_TopicBase):
  def __init__(self, client: 'Client', topic: int) -> None:
    super().__init__(client, topic)
    self._receiver = _InTopicReceiver(client, topic)
    self._a_is_paused = AsyncBool()
    self._cost: Optional[int] = None

  @property
  def is_paused(self): return self._a_is_paused.value
  @property
  def cost(self): return self._cost

  async def start(self): await self._receiver.start_recv()
  async def stop(self): await self._receiver.stop_recv()
  async def wait_paused(self, value: bool = True): return await self._a_is_paused.wait(value)
  async def recv_data(self):
    while True:
      data = await self.recv_data_control()
      if not isinstance(data, TopicControlData): return data 

  async def recv_data_control(self):
    while True:
      action, data = await self._receiver.recv()
      if action == _InTopicAction.DATA: return data
      if action == _InTopicAction.SET_CONTROL: 
        assert isinstance(data, TopicControlData)
        self._a_is_paused.set(data.paused)
        return data
      if action == _InTopicAction.SET_COST: self._cost = data

  async def _set_registered(self, registered: bool):
    if registered: await self._client.register_in_topics([ self._topic ])
    else: await self._client.unregister_in_topics([ self._topic ])

class _OutTopicAction(Enum):
  SET_REQUESTED = auto()

class _OutTopicReceiver(Receiver):
  _recv_queue: asyncio.Queue[(_OutTopicAction, Any)]

  def __init__(self, client: 'Client', topic: int):
    super().__init__(client)
    self._topic = topic

  def _put_msg(self, action: _OutTopicAction, data: Any):
    self._recv_queue.put_nowait((action, data))

  def on_message(self, message: Message):
    if isinstance(message, InTopicsChangedMessage):
      if self._topic in message.add: self._put_msg(_OutTopicAction.SET_REQUESTED, True)
      if self._topic in message.remove: self._put_msg(_OutTopicAction.SET_REQUESTED, False)

class OutTopic(_TopicBase):
  def __init__(self, client: 'Client', topic: int) -> None:
    super().__init__(client, topic)
    self._receiver = _OutTopicReceiver(client, topic)
    self._is_paused: bool = False
    self._a_is_requested = AsyncBool()
    self._receiver_task: Optional[asyncio.Task] = None

  @property
  def is_paused(self): return self._is_paused
  @property
  def is_requested(self): return self._a_is_requested.value

  async def start(self):
    if self._receiver_task is None: self._receiver_task = asyncio.create_task(self._run_receiver())
    await self._receiver.start_recv()

  async def stop(self):
    await self._receiver.stop_recv()
    if self._receiver_task is not None: 
      self._receiver_task.cancel()
      self._receiver_task = None

  async def wait_requested(self, value: bool = True): return await self._a_is_requested.wait(value)

  async def send(self, data: SerializableData): await self._client.send_stream_data(self._topic, data)
  async def set_paused(self, paused: bool):
    if paused != self._is_paused:
      self._is_paused = paused
      await self._client.send_stream_control(self._topic, TopicControlData(paused=paused))
  
  async def _set_registered(self, registered: bool):
    if registered: await self._client.register_out_topics([ self._topic ])
    else: await self._client.unregister_out_topics([ self._topic ])
  async def _run_receiver(self):
    while True:
      action, data = await self._receiver.recv()
      if action == _OutTopicAction.SET_REQUESTED:
        self._a_is_requested.set(data)

class InTopicsContext:
  def __init__(self, client: 'Client', topics: Iterable[int]):
    self._client = client
    self._topics = topics
  async def __aenter__(self): await self._client.register_in_topics(self._topics)
  async def __aexit__(self, *_): await self._client.unregister_in_topics(self._topics)
class OutTopicsContext:
  def __init__(self, client: 'Client', topics: Iterable[int]):
    self._client = client
    self._topics = topics
  async def __aenter__(self): await self._client.register_out_topics(self._topics)
  async def __aexit__(self, *_): await self._client.unregister_out_topics(self._topics)