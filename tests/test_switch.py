import unittest
from streamtasks.comm import *

class TestSwitch(unittest.IsolatedAsyncioTestCase):
  a: Connection
  b: Connection
  switch: Switch

  async def asyncSetUp(self):
    conn1 = create_local_cross_connector()
    conn2 = create_local_cross_connector()

    self.switch = Switch()
    await self.switch.add_connection(conn1[0])
    await self.switch.add_connection(conn2[0])
    
    self.a = conn1[1]
    self.b = conn2[1]

  async def test_standard_workflow(self):
    print("send")
    await self.a.send(OutTopicsChangedMessage(set([ PricedId(1, 0) ]), set()))
    await self.switch.process()

    await self.b.recv() # receive and ignore provides message

    self.assertIn(1, self.switch.connections[0].out_topics)

    await self.b.send(InTopicsChangedMessage(set([1]), set()))
    await self.switch.process()

    self.assertIn(1, self.switch.connections[1].in_topics)
    self.assertIn(1, self.switch.in_topics)

    await self.a.send(StreamDataMessage(1, "Hello"))
    await self.switch.process()

    received = await self.b.recv()
    self.assertEqual(received.data, "Hello")

    await self.b.send(InTopicsChangedMessage(set(), set([1])))
    await self.switch.process()

    self.assertNotIn(1, self.switch.in_topics)
    self.assertNotIn(1, self.switch.connections[1].in_topics)

    await self.a.send(StreamDataMessage(1, "Hello"))
    await self.switch.process()

    received = await self.b.recv()
    self.assertIsNone(received)
  
  async def test_provider_added(self):
    await self.b.send(InTopicsChangedMessage(set([1]), set()))
    await self.a.send(OutTopicsChangedMessage(set([ PricedId(1, 0) ]), set()))
    await self.switch.process()
    await self.b.recv() # receive and ignore provides message

    a_received = await self.a.recv()
    self.assertIsInstance(a_received, InTopicsChangedMessage)
    self.assertIn(1, a_received.add)

    await self.a.send(StreamDataMessage(1, "Hello"))
    await self.switch.process()
    
    b_received = await self.b.recv()
    self.assertEqual(b_received.data, "Hello")

  async def test_double_unsubscribe(self):
    await self.b.send(InTopicsChangedMessage(set([1]), set()))
    await self.switch.process()
    await self.b.send(InTopicsChangedMessage(set(), set([1])))
    await self.switch.process()
    await self.b.send(InTopicsChangedMessage(set(), set([1])))
    await self.switch.process()
  
  async def test_subscribe_flow(self):
    await self.a.send(OutTopicsChangedMessage(set([ PricedId(1, 0) ]), set()))
    await self.b.send(InTopicsChangedMessage(set([1]), set()))
    await self.switch.process()
    
    received = await self.a.recv()
    self.assertIsInstance(received, InTopicsChangedMessage)
    self.assertIn(1, received.add)

    await self.b.send(InTopicsChangedMessage(set([1]), set()))
    await self.switch.process()
    
    received = await self.a.recv()
    self.assertIsNone(received)

    await self.b.send(InTopicsChangedMessage(set(), set([1])))
    await self.switch.process()

    received = await self.a.recv()
    self.assertIsInstance(received, InTopicsChangedMessage)
    self.assertIn(1, received.remove)
    
  async def test_close(self):
    self.a.close()
    self.b.close()

    await self.switch.process()

    self.assertEqual(len(self.switch.connections), 0)

if __name__ == '__main__':
  unittest.main()