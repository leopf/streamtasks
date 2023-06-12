from dataclasses import dataclass
from typing import Any, Iterable
from abc import ABC

class Message(ABC):
  pass

class StreamMessage(Message, ABC):
  topic: int

@dataclass
class StreamDataMessage(StreamMessage):
  topic: int
  data: Any

@dataclass
class StreamControlMessage(StreamMessage):
  topic: int
  paused: bool

  def to_data(self) -> 'StreamControlData': return StreamControlData(self.paused)

@dataclass
class PricedId:
  id: int
  cost: int

  def __hash__(self):
    return self.cost | self.id << 32

@dataclass
class InTopicsChangedMessage(Message):
  add: set[int]
  remove: set[int]

@dataclass
class OutTopicsChangedMessage(Message):
  add: set[PricedId]
  remove: set[int]

@dataclass
class StreamControlData:
  paused: bool

  def to_message(self, topic: int) -> StreamControlMessage: return StreamControlMessage(topic, self.paused)

def merge_priced_topics(topics: Iterable[PricedId]) -> set[PricedId]:
  topic_map = {}
  for topic in topics:
    current = topic_map.get(topic.id, float("inf"))
    topic_map[topic.id] = min(current, topic.cost)

  return set(PricedId(topic, cost) for topic, cost in topic_map.items())