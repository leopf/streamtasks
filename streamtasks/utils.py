from abc import abstractmethod
from collections import deque
from contextlib import asynccontextmanager
import hashlib
import math
import threading
from types import CoroutineType
from typing import Any, Awaitable, Generic, Iterable, Optional, TypeVar
import asyncio
import time

from streamtasks.env import NODE_NAME

class AsyncTaskManager:
  def __init__(self) -> None: self._tasks: set[asyncio.Task] = set()
  def create(self, corroutine: CoroutineType):
    task = asyncio.create_task(corroutine)
    self._tasks.add(task)
    task.add_done_callback(self._tasks.discard)
    return task
  def cancel_all(self):
    for task in self._tasks: task.cancel()


class IdTracker:
  def __init__(self): self._map: dict[int, int] = {}
  def __contains__(self, id: int): return id in self._map
  def items(self) -> Iterable[int]: return self._map.keys()
  def add_many(self, ids: Iterable[int]):
    final = set()
    for id in ids:
      val = self._map.get(id, 0)
      if val == 0: final.add(id)
      self._map[id] = val + 1
    return final
  def remove_many(self, ids: Iterable[int], force: bool = False):
    if force:
      for id in ids: self._map.pop(id, None)
      return ids
    else:
      final = set()
      for id in ids:
        val = self._map.get(id, 0)
        if val == 0: continue
        elif val == 1:
          self._map.pop(id, None)
          final.add(id)
        else: self._map[id] = val - 1
      return final
  def change_many(self, add: Iterable[int], remove: Iterable[int]):
    return self.add_many(add), self.remove_many(remove)


class AwaitableIdTracker(IdTracker):
  def __init__(self):
    super().__init__()
    self._waiting_ids_added: dict[int, asyncio.Event] = {}
    self._waiting_ids_removed: dict[int, asyncio.Event] = {}

  def add_many(self, ids: Iterable[int]):
    added = super().add_many(ids)
    for id in added:
      event = self._waiting_ids_added.pop(id, None)
      if event is not None: event.set()
    return added

  def remove_many(self, ids: Iterable[int]):
    removed = super().remove_many(ids)
    for id in removed:
      event = self._waiting_ids_removed.pop(id, None)
      if event is not None: event.set()
    return removed

  async def wait_for_id_added(self, id: int):
    if id not in self._waiting_ids_added: self._waiting_ids_added[id] = asyncio.Event()
    return await self._waiting_ids_added[id].wait()

  async def wait_for_id_removed(self, id: int):
    if id not in self._waiting_ids_removed: self._waiting_ids_removed[id] = asyncio.Event()
    return await self._waiting_ids_removed[id].wait()


class AsyncTrigger:
  def __init__(self) -> None:
    self._futs: list[asyncio.Future] = []

  def wait(self):
    fut = asyncio.Future()
    self._futs.append(fut)
    return fut

  def trigger(self):
    for fut in self._futs:
      if not fut.done(): fut.set_result(None)
    self._futs.clear()


class AsyncBool:
  def __init__(self, initial_value: bool = False) -> None:
    self._value = initial_value
    self._change_trigger = AsyncTrigger()
  @property
  def value(self): return bool(self)
  def __bool__(self): return self._value
  def set(self, value: bool):
    if self.value != value:
      self._value = value
      self._change_trigger.trigger()
  async def wait(self, value: bool):
    if self._value == value: return True
    else: await self._change_trigger.wait()


class AsyncObservable:
  static_fields = set(["_change_trigger"])
  def __init__(self) -> None:
    self._change_trigger = AsyncTrigger()
  def __setattr__(self, name: str, value: Any) -> None:
    if name not in AsyncObservable.static_fields and (name not in self.__dict__ or value != self.__dict__[name]):
      super().__setattr__(name, value)
      self._change_trigger.trigger()
    else: super().__setattr__(name, value)

  async def wait_change(self): return await self._change_trigger.wait()
  def as_dict(self):
    return { k: v for k, v in self.__dict__.items() if k not in AsyncObservable.static_fields }


class AsyncObservableDict:
  def __init__(self, initial_value: Optional[dict]) -> None:
    self._change_trigger = AsyncTrigger()
    self._data = {} if initial_value is None else initial_value

  async def wait_change(self): return await self._change_trigger.wait()

  def __getitem__(self, key: Any): return self._data[key]
  def __delitem__(self, key: Any):
    del self._data[key]
    self._change_trigger.trigger()
  def __setitem__(self, key: Any, value: Any):
    if key not in self._data or self._data[key] != value:
      self._data[key] = value
      self._change_trigger.trigger()

T0 = TypeVar("T0")
class AsyncProducer(Generic[T0]):
  def __init__(self) -> None:
    self._task: asyncio.Task | None = None
    self._entered_count: int = 0
    self._consumers: set['AsyncConsumer[T0]'] = set()
    self._enter_lock = asyncio.Lock()
    self._ended: bool = False

  @abstractmethod
  async def run(self): pass

  def close_consumers(self):
    for consumer in self._consumers: consumer.close()

  def send_message(self, message: T0):
    for consumer in self._consumers: consumer.put(message)

  async def close(self):
    self._on_ended()
    self._stop()
    if self._task is not None:
      try: await self.wait_done()
      except EOFError: pass

  async def __aenter__(self):
    if self._ended: raise EOFError()
    async with self._enter_lock:
      self._entered_count += 1
      if self._entered_count == 1:
        if self._task is not None: await self.wait_done()
        self._task = asyncio.create_task(self._run())

  async def __aexit__(self, *_):
    async with self._enter_lock:
      self._entered_count = max(self._entered_count - 1, 0)
      if self._entered_count == 0:
        if self._task is not None:
          self._stop()
          try: await self.wait_done()
          finally:  self._task = None

  def _stop(self): self._task.cancel()
  async def _run(self):
    try:
      if self._ended: raise EOFError()
      await self.run()
    except EOFError:
      self._on_ended()
      raise
    except asyncio.CancelledError: pass

  def _on_ended(self):
    self._ended = True
    self.close_consumers()

  async def wait_done(self):
    try: await self._task
    except asyncio.CancelledError: pass

class AsyncMPProducer(AsyncProducer[T0]):
  def __init__(self) -> None:
    super().__init__()
    self.stop_event = threading.Event()
    self._loop: asyncio.BaseEventLoop
    self._lock = asyncio.Lock()

  async def run(self):
    try: await asyncio.shield(self._shielded_run())
    except asyncio.CancelledError: self.stop_event.set()

  @abstractmethod
  def run_sync(self): pass
  def send_message(self, message: Any): self._loop.call_soon_threadsafe(super().send_message, message)
  def close_consumers(self): self._loop.call_soon_threadsafe(super().close_consumers)
  async def wait_done(self):
    try: await super().wait_done()
    finally:
      await self._lock.acquire() # make sure the inner has actually ended
      self._lock.release()
  def _stop(self): self.stop_event.set()
  async def _shielded_run(self):
    async with self._lock:
      try:
        self._loop = asyncio.get_running_loop()
        await self._loop.run_in_executor(None, self.run_sync)
      finally: self.stop_event.clear()

T1 = TypeVar("T1")
class AsyncConsumer(Generic[T1]):
  def __init__(self, producer: AsyncProducer) -> None:
    self._producer = producer
    self._queue: deque[T1] = deque()
    self._trigger = AsyncTrigger()
    self._closed = False

  def register(self): self._producer._consumers.add(self)
  def unregister(self): self._producer._consumers.remove(self)

  async def get(self):
    if len(self._queue) != 0: return self._queue.popleft()
    if self._closed: raise EOFError()
    _fut = self._trigger.wait()
    async with self._producer:
      while len(self._queue) == 0 and not self._closed:
        await _fut
        _fut = self._trigger.wait()
      # TODO we need to do this in here to prevent double deques
      if self._closed: raise EOFError()
      return self._queue.popleft()

  def put(self, e: T1):
    if self.test_message(e):
      self._queue.append(e)
      self._trigger.trigger()

  def close(self):
    self._closed = True
    self._trigger.trigger()

  def test_message(self, message: T1) -> bool: return True

async def wait_with_dependencies(main: Awaitable, deps: Iterable[asyncio.Future]):
  main = asyncio.Task(main) if asyncio.iscoroutine(main) else main
  await asyncio.wait([main, *deps], return_when="FIRST_COMPLETED")
  if not main.done(): main.cancel()
  return main.result()

def get_timestamp_ms(): return time.time_ns() // 1000_000

def get_node_name_id(name: str):
  id_hash = hashlib.sha256()
  id_hash.update(name.encode("utf-8"))
  id_hash.update(NODE_NAME().encode("utf-8"))
  return id_hash.hexdigest()[:16]

class TimeSynchronizer:
  def __init__(self): self._time_offset = 0
  @property
  def time(self) -> int: return get_timestamp_ms() + self._time_offset
  def update(self, timestamp: int): self._time_offset = timestamp - get_timestamp_ms()
  def reset(self): self._time_offset = 0

class IdGenerator:
  def __init__(self, start: int, end: int) -> None:
    assert start < end, "start must me smaller than end"
    self._current, self._start, self._end = start, start, end
  def next(self):
    res = self._current
    self._current += 1
    if self._current >= self._end: self._current = self._start
    return res

def strip_nones_from_dict(data: dict): return { k: v for k, v in data.items() if v is not None }

@asynccontextmanager
async def context_task(coro):
  try:
    task = asyncio.create_task(coro)
    yield
  finally:
    task.cancel()
    try: await task
    except asyncio.CancelledError: pass

def make_json_serializable(v: Any):
  if isinstance(v, (str, int, bool)) or v is None: return v
  if isinstance(v, float):
    if math.isnan(v): return "NaN"
    else: return v
  if isinstance(v, (bytes, bytearray, memoryview)): return v.hex()
  try: v = dict(v)
  except (TypeError, ValueError): v = list(v)
  except: pass
  if isinstance(v, dict): return { make_json_serializable(k): make_json_serializable(v) for k, v in v.items() }
  if isinstance(v, list): return [ make_json_serializable(v) for v in v ]
  return repr(v)
