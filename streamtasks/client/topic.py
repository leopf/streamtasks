from abc import abstractmethod
import asyncio
from enum import Enum, auto
from typing import Any, Optional
from streamtasks.client import Client
from streamtasks.client.receiver import Receiver
from streamtasks.message.data import SerializableData
from streamtasks.net import Message
from streamtasks.net.types import InTopicsChangedMessage, OutTopicsChangedMessage, TopicControlData, TopicControlMessage, TopicDataMessage

class _TopicRegisterContext:
  def __init__(self, topic_obj: '_TopicBase') -> None: self._topic_obj = topic_obj
  async def __aenter__(self): await self._topic_obj.set_registered(True)
  async def __aexit__(self, **_): await self._topic_obj.set_registered(False)

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
  async def __aexit__(self, **_): await self.stop()

class _InTopicAction(Enum):
  SET_COST = auto()
  SET_CONTROL = auto()
  DATA = auto()

class _InTopicReceiver(Receiver):
  _recv_queue: asyncio.Queue[(_InTopicAction, Any)]

  def __init__(self, client: Client, topic: int):
    super().__init__(client)
    self._topic = topic

  def _put_msg(self, action: _InTopicAction, data: Any):
    self._recv_queue.put_nowait((action, data))

  def on_message(self, message: Message):
    if isinstance(message, OutTopicsChangedMessage):
      otc_message: OutTopicsChangedMessage = message
      if self._topic in otc_message.remove: self._put_msg(_InTopicAction.SET_COST, None)
      else:
        topic_price_map = { pid.id: pid.cost for pid in otc_message.add }
        if self._topic in topic_price_map: self._put_msg(_InTopicAction.SET_COST, topic_price_map[self._topic])

    if isinstance(message, TopicControlMessage):
      tc_message: TopicControlMessage = message
      if tc_message.topic == self._topic:
        self._put_msg(_InTopicAction.SET_CONTROL, tc_message.to_data())

    if isinstance(message, TopicDataMessage):
      td_message: TopicDataMessage = message
      if tc_message.topic == self._topic:
        self._put_msg(_InTopicAction.SET_CONTROL, td_message.data)


class InTopic(_TopicBase):
  def __init__(self, client: 'Client', topic: int) -> None:
    super().__init__(client, topic)
    self._receiver = _InTopicReceiver(client, topic)
    self._control_data: Optional[TopicControlData] = None
    self._cost: Optional[int] = None

  @property
  def cost(self): return self._cost
  @property
  def is_available(self): return self._cost is not None
  @property
  def is_paused(self): return False if self._control_data is None else self._control_data.paused
  
  async def start(self): await self._receiver.start_recv()
  async def stop(self): await self._receiver.stop_recv()

  async def recv(self):
    while True:
      action, data = await self._receiver.recv()
      if action == _InTopicAction.DATA: return data
      if action == _InTopicAction.SET_CONTROL: self._control_data = data
      if action == _InTopicAction.SET_COST: self._cost = data

  async def _set_registered(self, registered: bool):
    if registered: await self._client.register_in_topics([ self._topic ])
    else: await self._client.unregister_in_topics([ self._topic ])

class _OutTopicAction(Enum):
  SET_REQUESTED = auto()

class _OutTopicReceiver(Receiver):
  _recv_queue: asyncio.Queue[(_OutTopicAction, Any)]

  def __init__(self, client: Client, topic: int):
    super().__init__(client)
    self._topic = topic

  def _put_msg(self, action: _OutTopicAction, data: Any):
    self._recv_queue.put_nowait((action, data))

  def on_message(self, message: Message):
    if isinstance(message, InTopicsChangedMessage):
      itc_message: InTopicsChangedMessage = message
      if self._topic in itc_message.add: self._put_msg(_OutTopicAction.SET_REQUESTED, True)
      if self._topic in itc_message.remove: self._put_msg(_OutTopicAction.SET_REQUESTED, False)

class OutTopic(_TopicBase):
  def __init__(self, client: 'Client', topic: int) -> None:
    super().__init__(client, topic)
    self._receiver = _OutTopicReceiver(client, topic)
    self._is_paused: bool = False
    self._is_requested: bool = False
    self._receiver_task: Optional[asyncio.Task] = None

  @property
  def is_paused(self): return self._is_paused
  @property
  def is_requested(self): return self._is_requested

  async def start(self):
    if self._receiver_task is None: self._receiver_task = asyncio.create_task(self._receiver_task())
    await self._receiver.start_recv()

  async def stop(self):
    await self._receiver.stop_recv()
    if self._receiver_task is not None: 
      self._receiver_task.cancel()
      self._receiver_task = None

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
        self._is_requested = data