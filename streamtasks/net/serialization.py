import streamtasks.net.messages as messages
from typing import Union, Any
import msgpack

MESSAGES: list[type[messages.Message]] = [
  messages.TopicDataMessage,
  messages.TopicControlMessage,
  messages.AddressedMessage,
  messages.AddressesChangedMessage,
  messages.InTopicsChangedMessage,
  messages.OutTopicsChangedMessage,
]

MESSAGE_TYPE_ID_MAP = { t: idx for idx, t in enumerate(MESSAGES) }
TYPE_ID_MESSAGE_MAP = { idx: t for idx, t in enumerate(MESSAGES) }

def serialize_message(message: messages.Message) -> bytes: return msgpack.packb({ **message.as_dict(), "_id": MESSAGE_TYPE_ID_MAP[type(message)] })
def deserialize_message(raw: bytes) -> messages.Message:
  data = msgpack.unpackb(raw)
  return TYPE_ID_MESSAGE_MAP[data.pop("_id")].from_dict(data)

class RawData:
  def __init__(self, data: Union[Any, memoryview]): self._data, self._raw = (data, None) if not isinstance(data, (memoryview, bytes, bytearray)) else (None, data)

  @property
  def data(self):
    if self._data is None: self._data = self.deserialize()
    return self._data

  def serialize(self) -> memoryview: return self._raw if self._raw is not None else memoryview(self._serialize())
  def deserialize(self) -> Any: return self._data if self._data is not None else self._deserialize()
  def update(self): self._raw = None
  def copy(self): return self.__class__(memoryview(self.serialize()))

  def _deserialize(self) -> Any: return msgpack.unpackb(self._raw)
  def _serialize(self) -> bytes: return msgpack.packb(self._data)
