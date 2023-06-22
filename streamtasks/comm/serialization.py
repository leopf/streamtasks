from abc import ABC, abstractmethod, abstractproperty
from typing import Union, Any
import json
import pickle
import struct
from enum import Enum

import fastavro
from streamtasks.comm.types import *
from io import BytesIO

PRICED_ID_SCHEMA = fastavro.parse_schema({
    "type": "record",
    "name": "PricedId",
    "fields": [
        {"name": "id", "type": "int"},
        {"name": "cost", "type": "int"}
    ]
})
MESSAGE_SCHEMA_ID_MAP = {
    TopicDataMessage: 0,
    TopicControlMessage: 1,
    AddressedMessage: 2,
    AddressesChangedMessage: 3,
    InTopicsChangedMessage: 4,
    OutTopicsChangedMessage: 5,
}
SCHEMA_ID_MESSAGE_MAP = {v: k for k, v in MESSAGE_SCHEMA_ID_MAP.items()}

SCHEMA_MAP = {
    0: fastavro.parse_schema({
        "type": "record",
        "name": "TopicDataMessage",
        "fields": [
            {"name": "topic", "type": "int"},
            {"name": "data", "type": "bytes"}
        ]
    }),
    1: fastavro.parse_schema({
        "type": "record",
        "name": "TopicControlMessage",
        "fields": [
            {"name": "topic", "type": "int"},
            {"name": "paused", "type": "boolean"}
        ]
    }),
    2: fastavro.parse_schema({
        "type": "record",
        "name": "AddressedMessage",
        "fields": [
            {"name": "address", "type": "int"},
            {"name": "data", "type": "bytes"}
        ]
    }),
    3: fastavro.parse_schema({
        "type": "record",
        "name": "AddressesChangedMessage",
        "fields": [
            {"name": "add", "type": {"type": "array", "items": PRICED_ID_SCHEMA}},
            {"name": "remove", "type": {"type": "array", "items": "int"}}
        ]
    }),
    4: fastavro.parse_schema({
        "type": "record",
        "name": "InTopicsChangedMessage",
        "fields": [
            {"name": "add", "type": {"type": "array", "items": "int"}},
            {"name": "remove", "type": {"type": "array", "items": "int"}}
        ]
    }),
    5: fastavro.parse_schema({
        "type": "record",
        "name": "OutTopicsChangedMessage",
        "fields": [
            {"name": "add", "type": {"type": "array", "items": PRICED_ID_SCHEMA}},
            {"name": "remove", "type": {"type": "array", "items": "int"}}
        ]
    }),
}

def serialize_message(message: Message) -> bytes:
    stream = BytesIO()
    id = MESSAGE_SCHEMA_ID_MAP[type(message)]
    stream.write(bytes([id]))
    schema = SCHEMA_MAP[id]
    fastavro.schemaless_writer(stream, schema, message.as_dict())
    return stream.getvalue()

def deserialize_message(data: bytes) -> Message:
    stream = BytesIO(data)
    id = stream.read(1)[0]
    schema = SCHEMA_MAP[id]
    element = fastavro.schemaless_reader(stream, schema)
    return SCHEMA_ID_MESSAGE_MAP[id].from_dict(element)

# class SerializationType(Enum):
#   JSON = 1
#   PICKLE = 2
#   CUSTOM = 3

# class Serializable:
#   @abstractproperty
#   def type(self) -> SerializationType: pass

#   @abstractmethod
#   def serialize(self) -> bytes: pass

# class Deserializer:
#   @abstractmethod
#   def deserialize(self) -> Any: pass

# class SerializableData(Serializable, Deserializer, ABC):
#   _data: Any
#   _raw: bytes
#   def __init__(self, data: Union[Any, bytes]): self._data, self._raw = (data, None) if not isinstance(data, bytes) else (None, data)
#   @property
#   def data(self):
#     if self._data is None: self._data = self.deserialize()
#     return self._data

# class JsonData(SerializableData):
#   @property
#   def type(self) -> SerializationType: return SerializationType.JSON
#   def deserialize(self) -> Any: return json.loads(self._raw.decode("utf-8"))
#   def serialize(self) -> (int, bytes): return SerializationType.JSON, json.dumps(self._data).encode("utf-8")

# class PickleData(SerializableData):
#   @property
#   def type(self) -> SerializationType: return SerializationType.PICKLE
#   def deserialize(self) -> Any: return pickle.loads(self._raw)
#   def serialize(self) -> (int, bytes): return SerializationType.PICKLE, pickle.dumps(self._data)

# class CustomData(SerializableData):
#   def __init__(self, data: Union[Any, bytes], deserializer: Deserializer):
#     if isinstance(data, bytes):
#       id = struct.unpack("<H", data[:2])
#     self._deserializer = deserializer
#     super().__init__(data)
#   def deserialize(self) -> Any: pass
#   def serialize(self) -> (int, bytes): pass