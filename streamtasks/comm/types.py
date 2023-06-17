from dataclasses import dataclass
from typing import Any, Iterable
from abc import ABC

class Message(ABC):
  pass

class TopicMessage(Message, ABC):
  topic: int

@dataclass
class TopicDataMessage(TopicMessage):
  topic: int
  data: Any

@dataclass
class TopicControlMessage(TopicMessage):
  topic: int
  paused: bool

  def to_data(self) -> 'StreamControlData': return TopicControlData(self.paused)

@dataclass
class AddressedMessage(Message):
  address: int
  data: Any

@dataclass
class PricedId:
  id: int
  cost: int

  def __hash__(self):
    return self.cost | self.id << 32

@dataclass
class AddressesChangedMessage(Message):
  add: set[PricedId]
  remove: set[int]

@dataclass
class AddressesChangedRecvMessage(Message):
  add: set[PricedId]
  remove: set[PricedId]

@dataclass
class InTopicsChangedMessage(Message):
  add: set[int]
  remove: set[int]

@dataclass
class OutTopicsChangedMessage(Message):
  add: set[PricedId]
  remove: set[int]

@dataclass
class OutTopicsChangedRecvMessage(Message):
  add: set[PricedId]
  remove: set[PricedId]

@dataclass
class TopicControlData:
  paused: bool

  def to_message(self, topic: int) -> TopicControlMessage: return TopicControlMessage(topic, self.paused)
