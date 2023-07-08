from typing import Any, Callable, Optional
from streamtasks.comm.types import TopicControlData
from streamtasks.message import get_timestamp_from_message, SerializableData
import logging

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

class SynchronizedStream:
  def __init__(self, sync: 'StreamSynchronizer'):
    self.action_queue = []
    self.is_paused = False
    self.sync = sync

  @property
  def is_empty(self): return len(self.action_queue) == 0
  @property
  def timestamp(self): return self.action_queue[0][0] if len(self.action_queue) > 0 else 0
  @property
  def more_available(self): self.timestamp <= self.sync.sync_timestamp
  
  def pop_full(self):
    if self.timestamp > self.sync.sync_timestamp: return None, None, None
    timestamp, data, paused = self.action_queue.pop(0)
    if paused is not None: self.is_paused = paused
    self.sync.update_sync_timestamp()
    return timestamp, data, None if paused is None else TopicControlData(paused)
  def pop(self):
    _, data, control = self.pop_full()
    return data, control
  def add(data: Optional[SerializableData], control: Optional[TopicControlData], fail_safe: bool = True):
    try:
      if data is not None: self.add_data(data)
      if control is not None: self.add_control(control)
    except BaseException as e:
      if fail_safe: logging.error(f"Failed to add data to stream: {e}")
      else: raise e
  def add_data(self, data: SerializableData):
    timestamp = get_timestamp_from_message(data)
    self.action_queue.append((timestamp, data, None))
    self._sort_action_queue()
    self.sync.update_sync_timestamp()
  def add_control(self, control: TopicControlData):
    paused = control.paused
    if len(self.action_queue) == 0: self.action_queue.append((self.sync.sync_timestamp, None, True))
    timestamp, data, old_paused = self.action_queue.pop(-1)
    new_paused = paused if old_paused is None or old_paused == paused else None
    self.action_queue.append((timestamp, data, new_paused))
  def _sort_action_queue(self): self.action_queue.sort(key=lambda x: x[0])

class StreamSynchronizer:
  def __init__(self):
    self.streams = []
    self.sync_timestamp = 0

  def create_stream(self): 
    stream = SynchronizedStream(self)
    self.streams.append(stream)
    return stream

  def update_sync_timestamp(self):
    self.sync_timestamp = min((stream.timestamp for stream in self.streams if not stream.is_paused or not stream.is_empty), default=self.sync_timestamp)
      