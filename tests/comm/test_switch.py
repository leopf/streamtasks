import unittest
from streamtasks.comm import *
from streamtasks.message.data import *

class TestSwitch(unittest.IsolatedAsyncioTestCase):
  a: Connection
  b: Connection
  switch: Switch
  tasks: list[asyncio.Task]

  async def asyncSetUp(self):
    conn1 = create_local_cross_connector(raw=True)
    conn2 = create_local_cross_connector(raw=True)

    self.switch = Switch()
    await self.switch.add_connection(conn1[0])
    await self.switch.add_connection(conn2[0])

    self.switch_connections = [ conn1[0], conn2[0] ]
    self.a = conn1[1]
    self.b = conn2[1]
    self.tasks = []

  async def asyncTearDown(self):
    self.switch.close_all_connections()
    for task in self.tasks: task.cancel()

  async def test_standard_workflow(self):
    await self.a.send(OutTopicsChangedMessage(set([ PricedId(1, 0) ]), set()))

    await self.b.recv() # receive and ignore provides message

    self.assertIn(1, self.switch_connections[0].out_topics)

    await self.b.send(InTopicsChangedMessage(set([1]), set()))
    await self.a.recv()

    self.assertIn(1, self.switch_connections[1].in_topics)
    self.assertIn(1, self.switch.in_topics)

    await self.a.send(TopicDataMessage(1, TextData("Hello")))

    received = await self.b.recv()
    self.assertEqual(received.data.data, "Hello")

    await self.b.send(InTopicsChangedMessage(set(), set([1])))
    await self.a.recv()

    self.assertNotIn(1, self.switch.in_topics)
    self.assertNotIn(1, self.switch_connections[1].in_topics)
  
  async def test_provider_added(self):
    await self.b.send(InTopicsChangedMessage(set([1]), set()))
    await self.a.send(OutTopicsChangedMessage(set([ PricedId(1, 0) ]), set()))
    await self.b.recv() # receive and ignore provides message

    a_received = await self.a.recv()
    self.assertIsInstance(a_received, InTopicsChangedMessage)
    self.assertIn(1, a_received.add)

    await self.a.send(TopicDataMessage(1, TextData("Hello")))

    b_received = await self.b.recv()
    self.assertEqual(b_received.data.data, "Hello")

  async def test_double_unsubscribe(self):
    await self.a.send(OutTopicsChangedMessage(set([ PricedId(1, 0), PricedId(2, 0) ]), set()))
    await self.b.send(InTopicsChangedMessage(set([1, 2]), set()))
    await self.b.send(InTopicsChangedMessage(set(), set([1])))
    await self.b.send(InTopicsChangedMessage(set(), set([2, 1])))

    received = await self.a.recv()
    self.assertIsInstance(received, InTopicsChangedMessage)
    self.assertIn(1, received.add)

    received = await self.a.recv()
    self.assertIsInstance(received, InTopicsChangedMessage)
    self.assertIn(1, received.remove)

    received = await self.a.recv()
    self.assertIsInstance(received, InTopicsChangedMessage)
    self.assertIn(2, received.remove)
    self.assertNotIn(1, received.remove)
  
  async def test_subscribe_flow(self):
    await self.a.send(OutTopicsChangedMessage(set([ PricedId(1, 0) ]), set()))
    await self.b.send(InTopicsChangedMessage(set([1]), set()))
    
    received = await self.a.recv()
    self.assertIsInstance(received, InTopicsChangedMessage)
    self.assertIn(1, received.add)

    received = await self.b.recv()
    self.assertIsInstance(received, OutTopicsChangedRecvMessage)

    await self.b.send(InTopicsChangedMessage(set([1]), set()))
    await self.b.send(InTopicsChangedMessage(set(), set([1])))

    received = await self.a.recv()
    self.assertIsInstance(received, InTopicsChangedMessage)
    self.assertIn(1, received.remove)
    
  async def test_close(self):    
    async with asyncio.timeout(1):
      self.a.close()
      while len(self.switch.cm.connections) != 1: await asyncio.sleep(0.001)
      self.assertEqual(len(self.switch.cm.connections), 1)

      self.b.close()
      while len(self.switch.cm.connections) != 0: await asyncio.sleep(0.001)
      self.assertEqual(len(self.switch.cm.connections), 0)
    
if __name__ == '__main__':
  unittest.main()