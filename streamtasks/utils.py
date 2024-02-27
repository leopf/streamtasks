from types import CoroutineType
from typing import Any, ClassVar, Iterable, Optional
import asyncio
import time
import os
import functools
from contextlib import ContextDecorator


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
  _waiting_ids: dict[int, asyncio.Event]

  def __init__(self):
    super().__init__()
    self._waiting_ids_added = {}
    self._waiting_ids_removed = {}

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

  async def wait(self):
    fut = asyncio.Future()
    self._futs.append(fut)
    return await fut

  def trigger(self):
    for fut in self._futs: fut.set_result(None)
    self._futs.clear()


class AsyncBool:
  def __init__(self, initial_value: bool = False) -> None:
    self._value = initial_value
    self._change_trigger = AsyncTrigger()
  @property
  def value(self): return self._value
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


def get_timestamp_ms(): return int(time.time() * 1000)


class TimeSynchronizer:
  def __init__(self):
    self._time_offset = 0
  @property
  def time(self) -> int: return get_timestamp_ms() + self._time_offset
  def update(self, timestamp: int): self._time_offset = timestamp - get_timestamp_ms()
  def reset(self): self._time_offset = 0

# context stuff from https://github.com/tinygrad/tinygrad/blob/master/tinygrad/helpers.py


@functools.lru_cache(maxsize=None)
def getenv(key, default=0) -> Any: return type(default)(os.getenv(key, default))


class IdGenerator:
  def __init__(self, start: int, end: int) -> None:
    assert start < end, "start must me smaller than end"
    self._current, self._start, self._end = start, start, end
  def next(self):
    res = self._current
    self._current += 1
    if self._current >= self._end: self._current = self._start
    return res


class Context(ContextDecorator):
  def __init__(self, **kwargs): self.pvars = { k.upper(): v for k, v in kwargs.items() }
  def __enter__(self): ContextVar.ctx_stack.append({ **ContextVar.ctx_stack[-1].items(), **self.pvars })
  def __exit__(self, *args): ContextVar.ctx_stack.pop()


class ContextVar:
  ctx_stack: ClassVar[list[dict[str, Any]]] = [{}]
  def __init__(self, key, default_value):
    self.key, self.initial_value = key.upper(), getenv(key.upper(), default_value)
    if self.key not in ContextVar.ctx_stack[-1]: ContextVar.ctx_stack[-1][self.key] = self.initial_value
  def __call__(self, x): ContextVar.ctx_stack[-1][self.key] = x
  def __bool__(self): return bool(self.value)
  def __ge__(self, x): return self.value >= x
  def __gt__(self, x): return self.value > x
  @property
  def value(self): return ContextVar.ctx_stack[-1][self.key] if self.key in ContextVar.ctx_stack[-1] else self.initial_value


INSTANCE_ID = ContextVar('instance_id', "0")