from typing import Any, Callable, Optional
from streamtasks.comm.types import TopicControlData
from streamtasks.message import get_timestamp_from_message, SerializableData
from streamtasks.client.receiver import TopicsReceiver
import logging
import asyncio

class SynchronizedMessage:
  def __init__(self, controller: 'SynchronizedStreamController', timestamp: int, data: Optional[SerializableData], control: Optional[TopicControlData]):
    self.timestamp = timestamp
    self.data = data
    self.control = control
    self.controller = controller
  def __enter__(self): return self
  def __exit__(self, exc_type, exc_value, traceback): self.done()
  def done(self): self.controller.message_done()

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
  def has_messages_available(self): return self.timestamp <= self.sync.sync_timestamp and not self.is_empty
  
  def message_done(self):
    assert len(self.message_queue) > 0, "Cannot call message_done when there are no messages in the queue"
    timestamp, data, paused = self.message_queue.pop(0)
    if paused is not None: self.is_paused = paused
    self.sync.update_sync_timestamp()

  async def next(self):
    await self._messages_available.wait()
    timestamp, data, paused = self.message_queue[0]
    return SynchronizedMessage(self, timestamp, data, TopicControlData(paused=paused) if paused is not None else None)

  def add(self, data: Optional[SerializableData], control: Optional[TopicControlData], suppress_error: bool = True):
    try: 
      if data is not None: self._add_data(data)  
    except BaseException as e:
      if suppress_error: logging.error(f"Failed to add data to stream: {e}")
      else: raise e
    finally: 
      if control is not None: self._add_control(control)

  def update(self): 
    if self.has_messages_available: self._messages_available.set()
    else: self._messages_available.clear()

  def _add_data(self, data: SerializableData):
    timestamp = get_timestamp_from_message(data)
    changed_ts = timestamp < self.timestamp
    self.message_queue.append((timestamp, data, None))

    if len(self.message_queue) > 1: self._sort_action_queue() 
    if len(self.message_queue) > 1 or changed_ts: self.sync.update_sync_timestamp()

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
    assert len(list(receiver.topics)) == 1, "The behavior of a synchronized stream is undefined when multiple topics are subscribed to"
    self.sync = sync
    self.receiver = receiver
    self.controller = sync.create_stream_controller()
  async def __aenter__(self): 
    await self.receiver.__aenter__()
    return self
  async def __aexit__(self, exc_type, exc_value, traceback): await self.receiver.__aexit__(exc_type, exc_value, traceback)
  
  async def recv(self):
    recv_task = asyncio.create_task(self._run_receiver())
    message = await self.controller.next()
    recv_task.cancel()
    return message

  async def _run_receiver(self):
    try:
      while True:
        _, data, control = await self.receiver.get()
        self.controller.add(data, control)
    except asyncio.CancelledError: pass

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