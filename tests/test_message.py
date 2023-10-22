import unittest
from streamtasks.message import NumberMessage, MessagePackData, MediaPacketData, CustomData, get_timestamp_from_message, MediaPacket, SerializationType, data_from_serialization_type, get_core_serializers


class TestMessage(unittest.TestCase):
  def test_media_packet(self):
    core_serializers = get_core_serializers()
    packet = MediaPacket(b'hello', 1337, 0, False)
    data = MediaPacketData(packet)
    serialized = data.serialize()
    sdata = data_from_serialization_type(serialized, SerializationType.CUSTOM)
    self.assertIsInstance(sdata, CustomData)
    sdata.serializer = core_serializers[sdata.content_id]

    self.assertEqual(sdata.data.data.decode("utf-8"), packet.data.decode("utf-8"))
    self.assertEqual(sdata.data.timestamp, packet.timestamp)
    self.assertEqual(sdata.data.pts, packet.pts)
    self.assertEqual(sdata.data.rel_dts, packet.rel_dts)
    self.assertEqual(sdata.data.is_keyframe, packet.is_keyframe)

    self.assertEqual(get_timestamp_from_message(sdata), packet.timestamp)
    self.assertEqual(get_timestamp_from_message(data), packet.timestamp)

  def test_number_message(self):
    message = NumberMessage(timestamp=1337, value=42.0)
    data = MessagePackData(message.model_dump())
    serialized = data.serialize()
    sdata = data_from_serialization_type(serialized, SerializationType.MSGPACK)
    self.assertIsInstance(sdata, MessagePackData)
    self.assertEqual(sdata.data["timestamp"], message.timestamp)
    self.assertEqual(sdata.data["value"], message.value)
    self.assertEqual(get_timestamp_from_message(sdata), message.timestamp)
    self.assertEqual(get_timestamp_from_message(data), message.timestamp)


if __name__ == '__main__':
  unittest.main()
