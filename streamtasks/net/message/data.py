from abc import ABC, abstractmethod, abstractproperty
from typing import Union, Any, Optional
import json
import struct
import msgpack
from enum import Enum


class SerializationType(Enum):
  JSON = 1
  MSGPACK = 2
  TEXT = 3
  CUSTOM = 255


class Serializer:
  @abstractproperty
  def content_id(self) -> int: pass
  @abstractmethod
  def serialize(self, data: Any) -> memoryview: pass
  @abstractmethod
  def deserialize(self, data: memoryview) -> Any: pass


class SerializableData(ABC):
  def __init__(self, data: Union[Any, memoryview]): self._data, self._raw = (data, None) if not isinstance(data, (memoryview, bytes, bytearray)) else (None, data)
  @abstractproperty
  def type(self) -> SerializationType: pass
  @property
  def data(self):
    if self._data is None: self._data = self.deserialize()
    return self._data
  def serialize(self) -> memoryview: return self._raw if self._raw is not None else memoryview(self._serialize())
  def deserialize(self) -> Any: return self._data if self._data is not None else self._deserialize()
  def update(self): self._raw = None
  def copy(self): return self.__class__(memoryview(self.serialize()))
  @abstractmethod
  def _serialize(self) -> bytes: pass
  @abstractmethod
  def _deserialize(self) -> Any: pass


class JsonData(SerializableData):
  def __init__(self, data: Union[Any, memoryview]):
    if not isinstance(data, memoryview) and hasattr(data, "__dict__"):
      super().__init__(data.__dict__)
    else: super().__init__(data)
  @property
  def type(self) -> SerializationType: return SerializationType.JSON
  def _deserialize(self) -> Any: return json.loads(self._raw.tobytes().decode("utf-8"))
  def _serialize(self) -> bytes:
    return json.dumps(self._data if not hasattr(self._data, "__dict__") else self.data.__dict__).encode("utf-8")


class MessagePackData(SerializableData):
  @property
  def type(self) -> SerializationType: return SerializationType.MSGPACK
  def _deserialize(self) -> Any: return msgpack.unpackb(self._raw)
  def _serialize(self) -> bytes: return msgpack.packb(self._data)


class TextData(SerializableData):
  @property
  def type(self) -> SerializationType: return SerializationType.TEXT
  def _deserialize(self) -> Any: return self._raw.tobytes().decode("utf-8")
  def _serialize(self) -> bytes: return self._data.encode("utf-8")


class CustomData(SerializableData):
  serializer: Optional[Serializer]
  _content_id: Optional[int]

  def __init__(self, data: Union[Any, memoryview], serializer: Optional[Serializer] = None):
    self.serializer = serializer
    if isinstance(data, memoryview):
      self._content_id = struct.unpack("<H", data[:2])[0]
      super().__init__(data[2:])
    else:
      self._content_id = None
      super().__init__(data)

  @property
  def content_id(self) -> int:
    if self._content_id is None: self._content_id = self.serializer.content_id
    return self._content_id
  @property
  def type(self) -> SerializationType: return SerializationType.CUSTOM
  def _deserialize(self) -> Any:
    assert self.serializer is not None, "CustomData serializer not set"
    return self.serializer.deserialize(self._raw)
  def _serialize(self) -> bytes:
    assert self.serializer is not None, "CustomData serializer not set"
    return struct.pack("<H", self.content_id) + self.serializer.serialize(self.data)


def data_from_serialization_type(data: memoryview, t: SerializationType) -> SerializableData:
  if t == SerializationType.JSON: return JsonData(data)
  elif t == SerializationType.MSGPACK: return MessagePackData(data)
  elif t == SerializationType.TEXT: return TextData(data)
  elif t == SerializationType.CUSTOM: return CustomData(data)
  else: raise ValueError(f"Unknown serialization type {t}")