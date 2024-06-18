from dataclasses import dataclass
from typing import Any, TYPE_CHECKING, Self
from abc import ABC

if TYPE_CHECKING:
  from streamtasks.net.serialization import RawData

class Message(ABC):
  def as_dict(self) -> dict[str, Any]: return self.__dict__
  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> Self: return cls(**data)


class DataMessage(Message, ABC):
  data: 'RawData'

  def as_dict(self): return { **self.__dict__, 'data': self.data.serialize() }
  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> Self:
    from streamtasks.net.serialization import RawData
    inner_data = data['data'] if isinstance(data['data'], memoryview) else memoryview(data['data'])
    return cls(**{ **data, 'data': RawData(inner_data) })


class TopicMessage(Message, ABC):
  topic: int


@dataclass(frozen=True)
class TopicDataMessage(TopicMessage, DataMessage):
  topic: int
  data: 'RawData'


@dataclass(frozen=True)
class TopicControlMessage(TopicMessage):
  topic: int
  paused: bool

  def to_data(self) -> 'TopicControlData': return TopicControlData(self.paused)


@dataclass(frozen=True)
class AddressedMessage(DataMessage):
  address: int
  port: int
  data: 'RawData'


@dataclass(frozen=True)
class PricedId:
  id: int
  cost: int

  def __hash__(self):
    return self.cost | self.id << 32


@dataclass(frozen=True)
class AddressesChangedMessage(Message):
  add: set[PricedId]
  remove: set[int]

  def as_dict(self) -> dict[str, Any]:
    return {
      'add': list([ pid.__dict__ for pid in self.add ]),
      'remove': list(self.remove),
    }
  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> Self:
    return cls(
      add=set([ PricedId(**pid) for pid in data['add'] ]),
      remove=set(data['remove']),
    )


@dataclass(frozen=True)
class AddressesChangedRecvMessage(Message):
  add: set[PricedId]
  remove: set[PricedId]


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class OutTopicsChangedMessage(Message):
  add: set[PricedId]
  remove: set[int]

  def as_dict(self) -> dict[str, Any]:
    return {
      'add': list([ pid.__dict__ for pid in self.add ]),
      'remove': list(self.remove),
    }
  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> Self:
    return cls(
      add=set([ PricedId(**pid) for pid in data['add'] ]),
      remove=set(data['remove']),
    )


@dataclass(frozen=True)
class OutTopicsChangedRecvMessage(Message):
  add: set[PricedId]
  remove: set[PricedId]


@dataclass
class TopicControlData:
  paused: bool

  def to_message(self, topic: int) -> TopicControlMessage: return TopicControlMessage(topic, self.paused)
