from dataclasses import dataclass
from typing import Any, Iterable
from abc import ABC, abstractproperty, abstractclassmethod
from typing_extensions import Self

class Message(ABC):
  def as_dict(self) -> dict[str, Any]:
    return self.__dict__
  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> Self: return cls(**data)

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

  def as_dict(self) -> dict[str, Any]:
    return {
      'add': list([ pid.__dict__ for pid in self.add ]),
      'remove': list([ pid.__dict__ for pid in self.remove ]),
    }
  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> Self:
    return cls(
      add=set([ PricedId(**pid) for pid in data['add'] ]),
      remove=set([ pid['id'] for pid in data['remove'] ]),
    )

@dataclass
class AddressesChangedRecvMessage(Message):
  add: set[PricedId]
  remove: set[PricedId]

@dataclass
class InTopicsChangedMessage(Message):
  add: set[int]
  remove: set[int]

  def as_dict(self) -> dict[str, Any]:
    return {
      'add': list(self.add),
      'remove': list(self.remove),
    }
  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> Self:
    return cls(
      add=set(data['add']),
      remove=set(data['remove']),
    )

@dataclass
class OutTopicsChangedMessage(Message):
  add: set[PricedId]
  remove: set[int]

  def as_dict(self) -> dict[str, Any]:
    return {
      'add': list([ pid.__dict__ for pid in self.add ]),
      'remove': list([ pid.__dict__ for pid in self.remove ]),
    }
  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> Self:
    return cls(
      add=set([ PricedId(**pid) for pid in data['add'] ]),
      remove=set([ pid['id'] for pid in data['remove'] ]),
    )

@dataclass
class OutTopicsChangedRecvMessage(Message):
  add: set[PricedId]
  remove: set[PricedId]

@dataclass
class TopicControlData:
  paused: bool

  def to_message(self, topic: int) -> TopicControlMessage: return TopicControlMessage(topic, self.paused)
