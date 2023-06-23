from abc import ABC, abstractmethod, abstractproperty
from typing import Union, Any, Optional
import json
import pickle
import struct
from enum import Enum

class SerializationType(Enum):
  JSON = 1
  PICKLE = 2
  TEXT = 3
  CUSTOM = 255

class Serializable:
  @abstractproperty
  def type(self) -> SerializationType: pass

  @abstractmethod
  def serialize(self) -> bytes: pass

class Deserializable:
  @abstractmethod
  def deserialize(self) -> Any: pass

class Serializer:
  @abstractproperty
  def content_id(self) -> int: pass
  @abstractmethod
  def serialize(self, data: Any) -> bytes: pass
  @abstractmethod
  def deserialize(self, data: bytes) -> Any: pass

class SerializableData(Serializable, Deserializable, ABC):
  _data: Any
  _raw: bytes
  def __init__(self, data: Union[Any, bytes]): self._data, self._raw = (data, None) if not isinstance(data, bytes) else (None, data)
  @property
  def data(self):
    if self._data is None: self._data = self.deserialize()
    return self._data

class JsonData(SerializableData):
  @property
  def type(self) -> SerializationType: return SerializationType.JSON
  def deserialize(self) -> Any: return self._data if self._data is not None else json.loads(self._raw.decode("utf-8"))
  def serialize(self) -> bytes: return self._raw if self._raw is not None else json.dumps(self._data).encode("utf-8")

class PickleData(SerializableData):
  @property
  def type(self) -> SerializationType: return SerializationType.PICKLE
  def deserialize(self) -> Any: return self._data if self._data is not None else pickle.loads(self._raw)
  def serialize(self) -> bytes: return self._raw if self._raw is not None else pickle.dumps(self._data)

class TextData(SerializableData):
  @property
  def type(self) -> SerializationType: return SerializationType.TEXT
  def deserialize(self) -> Any: return self._data if self._data is not None else self._raw.decode("utf-8")
  def serialize(self) -> bytes: return self._raw if self._raw is not None else self._data.encode("utf-8")

class CustomData(SerializableData):
  serializer: Optional[Serializer]
  _content_id: Optional[int]
  
  def __init__(self, data: Union[Any, bytes]):
    self.serializer = None
    if isinstance(data, bytes):
      self._content_id = struct.unpack("<H", data[:2])
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
  def deserialize(self) -> Any:
    if self._data: return self.data
    assert self.serializer is not None, "CustomData serializer not set"
    return self.serializer.deserialize(self._raw)
  def serialize(self) -> bytes: 
    if self._raw: return self._raw
    assert self.serializer is not None, "CustomData serializer not set"
    return struct.pack("<H", self.content_id) + self.serializer.serialize(self.data)

def data_from_serialization_type(data: bytes, t: SerializationType):
  if t == SerializationType.JSON: return JsonData(data)
  elif t == SerializationType.PICKLE: return PickleData(data)
  elif t == SerializationType.TEXT: return TextData(data)
  elif t == SerializationType.CUSTOM: return CustomData(data)
  else: raise ValueError(f"Unknown serialization type {t}")