from abc import abstractmethod
import asyncio
from enum import Enum, auto
from typing import TYPE_CHECKING, Iterable, Optional
from streamtasks.client.receiver import Receiver
from streamtasks.utils import AsyncBool, AsyncTrigger
from streamtasks.net.serialization import RawData
from streamtasks.message.utils import get_timestamp_from_message
from streamtasks.net import Message
from streamtasks.net.messages import InTopicsChangedMessage, OutTopicsChangedMessage, TopicControlData, TopicControlMessage, TopicDataMessage, TopicMessage

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


class _InTopicReceiver(Receiver[tuple[_InTopicAction, None | int | TopicControlData | RawData]]):
  def __init__(self, client: 'Client', topic: int):
    super().__init__(client)
    self._topic = topic

  def _put_msg(self, action: _InTopicAction, data: None | int | TopicControlData | RawData): self._recv_queue.put_nowait((action, data))

  def on_message(self, message: Message):
    if isinstance(message, OutTopicsChangedMessage):
      if self._topic in message.remove: self._put_msg(_InTopicAction.SET_COST, None)
      else:
        new_cost = next((pid.cost for pid in message.add if pid.id == self._topic), None)
        if new_cost is not None: self._put_msg(_InTopicAction.SET_COST, new_cost)

    if isinstance(message, TopicMessage) and message.topic == self._topic:
      if isinstance(message, TopicControlMessage): self._put_msg(_InTopicAction.SET_CONTROL, message.to_data())
      if isinstance(message, TopicDataMessage): self._put_msg(_InTopicAction.DATA, message.data)

class InTopic(_TopicBase):
  def __init__(self, client: 'Client', topic: int, receiver: Optional[_InTopicReceiver] = None) -> None:
    super().__init__(client, topic)
    self._receiver = receiver if receiver else _InTopicReceiver(client, topic)
    self._a_is_paused = AsyncBool()
    self._cost: Optional[int] = None

  @property
  def is_paused(self): return self._a_is_paused.value
  @property
  def cost(self): return self._cost

  async def start(self): await self._receiver.start_recv()
  async def stop(self): await self._receiver.stop_recv()
  async def wait_paused(self, value: bool = True): return await self._a_is_paused.wait(value)
  async def recv_data(self) -> RawData:
    while True:
      data = await self.recv_data_control()
      if not isinstance(data, TopicControlData): return data

  async def recv_data_control(self) -> TopicControlData | RawData:
    while True:
      action, data = await self._receiver.get()
      if action == _InTopicAction.DATA: return data
      if action == _InTopicAction.SET_CONTROL:
        assert isinstance(data, TopicControlData)
        self._a_is_paused.set(data.paused)
        return data
      if action == _InTopicAction.SET_COST: self._cost = data
  async def _set_registered(self, registered: bool):
    if registered: await self._client.register_in_topics([ self._topic ])
    else: await self._client.unregister_in_topics([ self._topic ])

class InTopicSynchronizer:
  @abstractmethod
  async def wait_for(self, topic_id: int, timestamp: int) -> bool: pass
  @abstractmethod
  async def set_paused(self, topic_id: int, paused: bool): pass
  def start_receive(self, topic_id: int): pass

class SequentialInTopicSynchronizer(InTopicSynchronizer):
  def __init__(self) -> None:
    super().__init__()
    self._topic_timestamps: dict[int, int] = {}
    self._timestamp_trigger = AsyncTrigger()

  @property
  def min_timestamp(self): return 0 if len(self._topic_timestamps) == 0 else min(self._topic_timestamps.values())

  async def wait_for(self, topic_id: int, timestamp: int) -> bool:
    if timestamp < self._topic_timestamps.get(topic_id, 0): return False # NOTE: drop the past
    self._set_topic_timestamp(topic_id, timestamp)
    while self._is_waiting(topic_id, timestamp): await self._timestamp_trigger.wait()
    return True

  async def set_paused(self, topic_id: int, paused: bool):
    if paused: self._set_topic_timestamp(topic_id, None)
    else: self._set_topic_timestamp(topic_id, self.min_timestamp)

  def _is_waiting(self, topic_id: int, timestamp: int): return self.min_timestamp < timestamp
  def _set_topic_timestamp(self, topic_id: int, timestamp: int | None):
    if timestamp is None: self._topic_timestamps.pop(topic_id, None)
    else: self._topic_timestamps[topic_id] = timestamp
    self._timestamp_trigger.trigger()

class PrioritizedSequentialInTopicSynchronizer(SequentialInTopicSynchronizer):
  def __init__(self) -> None:
    super().__init__()
    self._topic_priorities: dict[int, int] = {}
    self._done_topics = set()

  async def wait_for(self, topic_id: int, timestamp: int) -> bool:
    if topic_id is self._done_topics: self._done_topics.remove(topic_id)
    return await super().wait_for(topic_id, timestamp)

  def start_receive(self, topic_id: int):
    self._done_topics.add(topic_id)
    self._timestamp_trigger.trigger()
    return super().start_receive(topic_id)

  def set_priority(self, topic_id: int, priority: int):
    self._topic_priorities[topic_id] = priority

  def _is_waiting(self, topic_id: int, timestamp: int):
    min_timestamp = self.min_timestamp
    if min_timestamp < timestamp: return True
    if len(self._topic_priorities) == 0: return False
    priority = self._topic_priorities.get(topic_id, 0)
    return any(True for tid, timestamp in self._topic_timestamps.items() if tid != topic_id and timestamp == min_timestamp and tid not in self._done_topics and self._topic_priorities.get(tid, 0) > priority)

class _SynchronizedInTopicReceiver(_InTopicReceiver):
  def __init__(self, client: 'Client', topic: int, sync: InTopicSynchronizer):
    super().__init__(client, topic)
    self._sync = sync

  async def get(self):
    while True:
      self._sync.start_receive(self._topic)
      action, data = await super().get()
      if action == _InTopicAction.SET_CONTROL:
        assert isinstance(data, TopicControlData)
        await self._sync.set_paused(self._topic, data.paused)
        return (action, data)
      elif action == _InTopicAction.DATA:
        try:
          timestamp = get_timestamp_from_message(data)
          if await self._sync.wait_for(self._topic, timestamp): return (action, data)
        except ValueError: pass

class SynchronizedInTopic(InTopic):
  def __init__(self, client: 'Client', topic: int, sync: InTopicSynchronizer) -> None:
    super().__init__(client, topic, _SynchronizedInTopicReceiver(client, topic, sync))

class _OutTopicAction(Enum):
  SET_REQUESTED = auto()


class _OutTopicReceiver(Receiver[tuple[_OutTopicAction, bool]]):
  def __init__(self, client: 'Client', topic: int):
    super().__init__(client)
    self._topic = topic

  def _put_msg(self, action: _OutTopicAction, data: bool): self._recv_queue.put_nowait((action, data))
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

  async def send(self, data: RawData): await self._client.send_stream_data(self._topic, data)
  async def set_paused(self, paused: bool):
    if paused != self._is_paused:
      self._is_paused = paused
      await self._client.send_stream_control(self._topic, TopicControlData(paused=paused))

  async def _set_registered(self, registered: bool):
    if registered: await self._client.register_out_topics([ self._topic ])
    else: await self._client.unregister_out_topics([ self._topic ])
  async def _run_receiver(self):
    while True:
      action, data = await self._receiver.get()
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
