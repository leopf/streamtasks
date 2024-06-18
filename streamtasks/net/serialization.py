import streamtasks.net.messages as messages
from typing import Any, ByteString
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

if __debug__:
  from datetime import datetime
  def _debug_is_msgpack_compatible(data: Any):
    if data is None: return True
    return isinstance(data, (str, int, float, bytes, bytearray, memoryview, bool, dict, list, tuple, datetime, msgpack.ext.ExtType, msgpack.ext.Timestamp))

class RawData:
  def __init__(self, data: ByteString | Any):
    assert data is not None, "None not allowed as RawData!"
    self._data, self._raw = (data, None) if not isinstance(data, (memoryview, bytes, bytearray)) else (None, data)
    assert _debug_is_msgpack_compatible(self._data), "Message pack data is not serializable"
  @property
  def data(self): return self.deserialize()
  def serialize(self) -> memoryview:
    if self._raw is None: self._raw = memoryview(msgpack.packb(self._data, strict_types=False)) # NOTE: do we want strict types?
    return self._raw
  def deserialize(self) -> Any:
    if self._data is None: self._data = msgpack.unpackb(self._raw)
    return self._data
  def update(self):
    self.deserialize()
    self._raw = None
  def copy(self): return RawData(memoryview(self.serialize()))

def to_raw_data(data: Any) -> RawData:
  if isinstance(data, RawData): return data
  assert _debug_is_msgpack_compatible(data), "Message pack data is not serializable"
  return RawData(data)
