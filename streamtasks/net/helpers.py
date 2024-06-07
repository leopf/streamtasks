from typing import Iterable
from streamtasks.net.messages import PricedId
from itertools import chain


class PricedIdTracker:
  _map: dict[int, dict[int, int]]
  _computed_map: dict[int, int]

  def __init__(self):
    self._map = {}
    self._computed_map = {}

  def __contains__(self, id: int): return id in self._computed_map
  def items(self) -> Iterable[PricedId]: return (PricedId(id, cost) for id, cost in self._computed_map.items())
  def get(self, id: int) -> int: return self._computed_map.get(id, float("inf"))

  def add_many(self, ids: Iterable[PricedId]) -> set[PricedId]:
    final = set()
    for id in ids:
      inner = self._map.get(id.id, None)
      if inner is None: inner = self._map[id.id] = {}
      inner[id.cost] = inner.get(id.cost, 0) + 1

      val = self._computed_map.get(id.id, float("inf"))
      if id.cost < val:
        self._computed_map[id.id] = id.cost
        final.add(id)
    return final

  def remove_many(self, ids: Iterable[PricedId]) -> tuple[set[int], set[PricedId]]:
    final_removed = set()
    final_updated = set()
    for id in ids:
      inner = self._map.get(id.id, None)
      if inner is None: continue
      val = inner.get(id.cost, 0)
      if val == 0: continue
      if val == 1:
        inner.pop(id.cost, None)
        if len(inner) == 0:
          self._map.pop(id.id, None)
          self._computed_map.pop(id.id, None)
          final_removed.add(id.id)
        else:
          min_cost = min(inner.keys())
          self._computed_map[id.id] = min_cost
          final_updated.add(PricedId(id.id, min_cost))
      else:
        inner[id.cost] = val - 1

    return final_removed, final_updated

  def change_many(self, add: Iterable[PricedId], remove: Iterable[PricedId]) -> tuple[set[PricedId], set[int]]:
    removed, updated = self.remove_many(remove)
    return merge_priced_topics(chain(iter(self.add_many(add)), iter(updated))), removed


def ids_to_priced_ids(ids: set[int], cost: int = 0):
  return set(PricedId(id, cost) for id in ids)


def merge_priced_topics(topics: Iterable[PricedId]) -> set[PricedId]:
  topic_map = {}
  for topic in topics:
    current = topic_map.get(topic.id, float("inf"))
    topic_map[topic.id] = min(current, topic.cost)

  return set(PricedId(topic, cost) for topic, cost in topic_map.items())
