from typing import Any, Callable, Optional
from streamtasks.comm.types import TopicControlData
from streamtasks.message import get_timestamp_from_message, SerializableData
from streamtasks.client.receiver import TopicsReceiver
import logging
import asyncio

class StreamValueTracker:
  def __init__(self):
    self.values = []
    self._stale = False
    self._in_timeframe = False
  def reset(self): 
    self.values.clear()
    self._stale = False
    self._in_timeframe = False
  def pop(self, timestamp: int, default=None):
    if len(self.values) == 0 or timestamp < self.values[0][0]: 
      self._in_timeframe = False
      return default
    self._in_timeframe = True
    while len(self.values) > 1 and self.values[1][0] <= timestamp: self.values.pop(0)
    if len(self.values) == 1 and self._stale: return default
    return self.values[0][1]
  def add(self, timestamp: int, value: Any):
    self._stale = False
    self.values.append((timestamp, value))
    self.values.sort(key=lambda x: x[0])
  def set_stale(self): self._stale = True
  def has_value(self, predicate: Callable[[int, Any], bool], default_value=None) -> bool: 
    if len(self.values) == 0: return predicate(0, default_value)
    if len(self.values) == 1 and self._stale and self._in_timeframe: return predicate(self.values[0][0], default_value)
    return any(predicate(*entry) for entry in self.values)

class SynchronizedStreamController:
  def __init__(self, sync: 'StreamSynchronizer'):
    self.message_queue = []
    self.is_paused = False
    self.sync = sync
    self._messages_available = asyncio.Event()

  @property
  def is_empty(self): return len(self.message_queue) == 0
  @property
  def timestamp(self): return self.message_queue[0][0] if len(self.message_queue) > 0 else 0
  @property
  def has_messages_available(self): self.timestamp <= self.sync.sync_timestamp
  
  async def pop(self):
    await self._messages_available.wait()
    timestamp, data, paused = self.message_queue.pop(0)
    if paused is not None: self.is_paused = paused
    self.sync.update_sync_timestamp()
    return data, None if paused is None else TopicControlData(paused)

  def add(self, data: Optional[SerializableData], control: Optional[TopicControlData], suppress_error: bool = True):
    try: 
      if data is not None: self._add_data(data)  
    except BaseException as e:
      if suppress_error: logging.error(f"Failed to add data to stream: {e}")
      else: raise e
    finally: 
      if control is not None: self._add_control(control)
      self.sync.update_sync_timestamp()

  def update(self): self._messages_available.set() if self.has_messages_available else self._messages_available.clear()
  
  def _add_data(self, data: SerializableData):
    timestamp = get_timestamp_from_message(data)
    self.message_queue.append((timestamp, data, None))
    self._sort_action_queue()
  def _add_control(self, control: TopicControlData):
    paused = control.paused
    if len(self.message_queue) == 0: self.message_queue.append((self.sync.sync_timestamp, None, True))
    timestamp, data, old_paused = self.message_queue.pop(-1)
    new_paused = paused if old_paused is None or old_paused == paused else None
    self.message_queue.append((timestamp, data, new_paused))
  def _sort_action_queue(self): self.message_queue.sort(key=lambda x: x[0])

class SynchronizedStream:
  def __init__(self, sync: 'StreamSynchronizer', receiver: TopicsReceiver):
    assert isinstance(receiver, TopicsReceiver)
    assert len(receiver.topics) == 1, "The behavior of a synchronized stream is undefined when multiple topics are subscribed to"
    self.sync = sync
    self.receiver = receiver
    self.controller = sync.create_stream_controller()

  async def recv(self):
    recv_task = asyncio.create_task(self._run_receiver())
    data, control = await self.controller.pop()
    recv_task.cancel()
    return data, control

  async def _run_receiver(self):
    while True:
      _, data, control = await self.receiver.get()
      self.controller.add(data, control)

class StreamSynchronizer:
  def __init__(self):
    self.stream_controllers = []
    self.sync_timestamp = 0

  def create_stream_controller(self): 
    stream_controller = SynchronizedStreamController(self)
    self.stream_controllers.append(stream_controller)
    return stream_controller

  def update_sync_timestamp(self):
    self.sync_timestamp = min((stream.timestamp for stream in self.stream_controllers if not stream.is_paused or not stream.is_empty), default=self.sync_timestamp)
    for stream in self.stream_controllers: stream.update()