import unittest
from streamtasks.communication import *

class TestSwitch(unittest.TestCase):
  a: TopicConnection
  b: TopicConnection
  switch: TopicSwitch

  def setUp(self):
    conn1 = create_local_cross_connector()
    conn2 = create_local_cross_connector()

    self.switch = TopicSwitch()
    self.switch.add_connection(conn1[0])
    self.switch.add_connection(conn2[0])
    
    self.a = conn1[1]
    self.b = conn2[1]

  def send_message_process(self, connection: TopicConnection, message: Message):
    connection.send(message)
    self.switch.process()

  def test_standard_workflow(self):
    self.send_message_process(self.a, ProvidesMessage(set([ 1 ]), set()))
    
    self.assertIn(1, self.switch.connections[0].out_topics)

    self.send_message_process(self.b, SubscribeMessage(1))

    self.assertIn(1, self.switch.connections[1].in_topics)
    self.assertEqual(self.switch.subscription_counter.get(1), 1)

    self.send_message_process(self.a, StreamMessage(1, "Hello"))

    received = self.b.recv()
    self.assertEqual(received.data, "Hello")

    self.send_message_process(self.b, UnsubscribeMessage(1))

    self.assertEqual(self.switch.subscription_counter.get(1), 0)
    self.assertNotIn(1, self.switch.connections[1].in_topics)

    self.send_message_process(self.a, StreamMessage(1, "Hello"))

    received = self.b.recv()
    self.assertIsNone(received)
  def test_provider_added(self):
    self.send_message_process(self.b, SubscribeMessage(1))
    self.send_message_process(self.a, ProvidesMessage(set([ 1 ]), set()))

    a_received = self.a.recv()
    self.assertIsInstance(a_received, SubscribeMessage)
    self.assertEqual(a_received.topic, 1)

    self.send_message_process(self.a, StreamMessage(1, "Hello"))

    b_received = self.b.recv()
    self.assertEqual(b_received.data, "Hello")
  def test_double_unsubscribe(self):
    self.send_message_process(self.b, SubscribeMessage(1))
    self.send_message_process(self.b, UnsubscribeMessage(1))
    self.send_message_process(self.b, UnsubscribeMessage(1))
  
  def test_subscribe_flow(self):
    self.send_message_process(self.a, ProvidesMessage(set([ 1 ]), set()))
    self.send_message_process(self.b, SubscribeMessage(1))
    
    received = self.a.recv()
    self.assertIsInstance(received, SubscribeMessage)
    self.assertEqual(received.topic, 1)

    self.send_message_process(self.b, SubscribeMessage(1))
    
    received = self.a.recv()
    self.assertIsNone(received)

    self.send_message_process(self.b, UnsubscribeMessage(1))

    received = self.a.recv()
    self.assertIsInstance(received, UnsubscribeMessage)
    self.assertEqual(received.topic, 1)
    
  def test_close(self):
    self.a.close()
    self.b.close()

    self.switch.process()

    self.assertEqual(len(self.switch.connections), 0)

if __name__ == '__main__':
  unittest.main()