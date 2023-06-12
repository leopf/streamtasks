import unittest
from streamtasks.comm import *
from streamtasks.messages import *

class TestSwitch(unittest.TestCase):
  a: Connection
  b: Connection
  switch: Switch

  def setUp(self):
    conn1 = create_local_cross_connector()
    conn2 = create_local_cross_connector()

    self.switch = Switch()
    self.switch.add_connection(conn1[0])
    self.switch.add_connection(conn2[0])
    
    self.a = conn1[1]
    self.a.ignore_internal = True
    self.b = conn2[1]
    self.b.ignore_internal = True

  def send_message_process(self, connection: Connection, message: Message):
    connection.send(message)
    self.switch.process()

  def test_standard_workflow(self):
    self.send_message_process(self.a, OutTopicsChangedMessage(set([ PricedId(1, 0) ]), set()))
    self.b.recv() # receive and ignore provides message
    
    self.assertIn(1, self.switch.connections[0].out_topics)

    self.send_message_process(self.b, InTopicsChangedMessage(set([1]), set()))

    self.assertIn(1, self.switch.connections[1].in_topics)
    self.assertEqual(self.switch.in_topics.get(1), 1)

    self.send_message_process(self.a, StreamDataMessage(1, "Hello"))

    received = self.b.recv()
    self.assertEqual(received.data, "Hello")

    self.send_message_process(self.b, InTopicsChangedMessage(set(), set([1])))

    self.assertEqual(self.switch.in_topics.get(1), 0)
    self.assertNotIn(1, self.switch.connections[1].in_topics)

    self.send_message_process(self.a, StreamDataMessage(1, "Hello"))

    received = self.b.recv()
    self.assertIsNone(received)
  
  def test_provider_added(self):
    self.send_message_process(self.b, InTopicsChangedMessage(set([1]), set()))
    self.send_message_process(self.a, OutTopicsChangedMessage(set([ PricedId(1, 0) ]), set()))
    self.b.recv() # receive and ignore provides message

    a_received = self.a.recv()
    self.assertIsInstance(a_received, InTopicsChangedMessage)
    self.assertIn(1, a_received.add)

    self.send_message_process(self.a, StreamDataMessage(1, "Hello"))
    
    b_received = self.b.recv()
    self.assertEqual(b_received.data, "Hello")

  def test_double_unsubscribe(self):
    self.send_message_process(self.b, InTopicsChangedMessage(set([1]), set()))
    self.send_message_process(self.b, InTopicsChangedMessage(set(), set([1])))
    self.send_message_process(self.b, InTopicsChangedMessage(set(), set([1])))
  
  def test_subscribe_flow(self):
    self.send_message_process(self.a, OutTopicsChangedMessage(set([ PricedId(1, 0) ]), set()))
    self.send_message_process(self.b, InTopicsChangedMessage(set([1]), set()))
    
    received = self.a.recv()
    self.assertIsInstance(received, InTopicsChangedMessage)
    self.assertIn(1, received.add)

    self.send_message_process(self.b, InTopicsChangedMessage(set([1]), set()))
    
    received = self.a.recv()
    self.assertIsNone(received)

    self.send_message_process(self.b, InTopicsChangedMessage(set(), set([1])))

    received = self.a.recv()
    self.assertIsInstance(received, InTopicsChangedMessage)
    self.assertIn(1, received.remove)
    
  def test_close(self):
    self.a.close()
    self.b.close()

    self.switch.process()

    self.assertEqual(len(self.switch.connections), 0)

if __name__ == '__main__':
  unittest.main()