from typing import Iterable
import asyncio
import time

class IdTracker:
  _map: dict[int, int]

  def __init__(self):
    self._map = {}

  def __contains__(self, id: int): return id in self._map
  def items(self) -> Iterable[int]: return self._map.keys()

  def add_many(self, ids: Iterable[int]):
    final = set()
    for id in ids:
      val = self._map.get(id, 0)
      if val == 0: final.add(id)
      self._map[id] = val + 1
    return final

  def remove_many(self, ids: Iterable[int]):
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

def get_timestamp_ms(): return int(time.time() * 1000)

class TimeSynchronizer:
  def __init__(self):
    self._time_offset = 0
  @property
  def time(self) -> int: return get_timestamp_ms() + self._time_offset
  def set_time(self, timestamp): self._time_offset = timestamp - get_timestamp_ms()
  def reset(self): self._time_offset = 0