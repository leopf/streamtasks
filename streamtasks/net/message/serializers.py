from streamtasks.net.message.data import Serializer, CustomData
from streamtasks.net.message.structures import MediaPacket
import fastavro
from io import BytesIO
from typing import Any, Union

"""
The core system uses the namespace 1000-1999 for content ids.
"""


class MediaPacketSerializer(Serializer):
  avro_schema = fastavro.schema.parse_schema({
    "type": "record",
    "name": "MediaPacket",
    "fields": [
      {"name": "timestamp", "type": "long"},
      {"name": "pts", "type": ["null", "long"]},
      {"name": "rel_dts", "type": ["null", "int"]},
      {"name": "is_keyframe", "type": "boolean"},
      {"name": "data", "type": "bytes"}
    ]
  })
  @property
  def content_id(self) -> int: return 1000
  def serialize(self, data: Any) -> memoryview:
    data: MediaPacket = data
    assert isinstance(data, MediaPacket)
    stream = BytesIO()
    fastavro.schemaless_writer(stream, self.avro_schema, data.as_dict())
    return memoryview(stream.getvalue())
  def deserialize(self, data: memoryview) -> Any:
    stream = BytesIO(data)
    return MediaPacket(**fastavro.schemaless_reader(stream, self.avro_schema))


class MediaPacketData(CustomData):
  def __init__(self, data: Union[Any, memoryview]): super().__init__(data, MediaPacketSerializer())


def get_core_serializers() -> dict[int, Serializer]:
  serializers = [MediaPacketSerializer()]
  return { serializer.content_id: serializer for serializer in serializers }