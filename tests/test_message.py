import unittest
from streamtasks.net.message.data import MessagePackData, SerializationType, data_from_serialization_type
from streamtasks.net.message.utils import get_timestamp_from_message
from streamtasks.net.message.structures import NumberMessage


class TestMessage(unittest.TestCase):
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
