from streamtasks.comm.types import *
from io import BytesIO
import struct
import fastavro
import avro.schema
from avro.datafile import DataFileReader, DataFileWriter

PricedIdSchema = fastavro.parse_schema({
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
            {"name": "add", "type": {"type": "array", "items": PricedIdSchema}},
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
            {"name": "add", "type": {"type": "array", "items": PricedIdSchema}},
            {"name": "remove", "type": {"type": "array", "items": "int"}}
        ]
    }),
}


def serialize_message(message: Message) -> bytes:
    stream = BytesIO()
    id = MESSAGE_SCHEMA_ID_MAP[type(message)]
    stream.write(struct.pack("<B", id))
    schema = SCHEMA_MAP[id]
    fastavro.schemaless_writer(stream, schema, message.__dict__)
    return stream.getvalue()

def deserialize_message(data: bytes) -> Message:
    stream = BytesIO(data)
    id = struct.unpack("<B", stream.read(1))[0]
    schema = SCHEMA_MAP[id]
    element = fastavro.schemaless_reader(stream, schema)
    return SCHEMA_ID_MESSAGE_MAP[id](**element)

message = TopicControlMessage(133337, True)# TopicDataMessage(1, b'hello')
serialized = serialize_message(message)
deserialized = deserialize_message(serialized)
print(deserialized)
