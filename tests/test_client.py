import unittest
from streamtasks.comm import *
from streamtasks.client import *

class TestClient(unittest.IsolatedAsyncioTestCase):
  a: Client
  b: Client
  stop_signal: asyncio.Event
  tasks: list[asyncio.Task]
  
  async def asyncSetUp(self):
    conn1 = create_local_cross_connector(raw=False)
    conn2 = create_local_cross_connector(raw=True)

    switch = Switch()
    await switch.add_connection(conn1[0])
    await switch.add_connection(conn2[0])

    self.tasks = []
    self.stop_signal = asyncio.Event()
    self.tasks.append(create_switch_processing_task(switch, self.stop_signal))
    
    self.a = Client(conn1[1])
    self.b = Client(conn2[1])

  async def asyncTearDown(self):
    self.stop_signal.set()
    for task in self.tasks: await task

  async def test_provide_subscribe(self):
    await self.a.provide([ 1, 2 ])
    await self.b.subscribe([ 1, 2 ])

    await self.a.send_stream_data(1, TextData("Hello 1"))
    await self.a.send_stream_data(2, TextData("Hello 2"))

    b_recv = self.b.get_topics_receiver([ 1, 2 ])

    recv_data = await asyncio.wait_for(b_recv.recv(), 1)
    self.assertEqual((recv_data[0], recv_data[1].data, recv_data[2]), (1, "Hello 1", None))

    recv_data = await asyncio.wait_for(b_recv.recv(), 1)
    self.assertEqual((recv_data[0], recv_data[1].data, recv_data[2]), (2, "Hello 2", None))

    await self.b.unsubscribe([ 1 ])
    await asyncio.sleep(0.001)

    await self.a.send_stream_data(1, TextData("Hello 1"))
    await self.a.send_stream_data(2, TextData("Hello 2"))

    recv_data = await asyncio.wait_for(b_recv.recv(), 1)
    self.assertEqual((recv_data[0], recv_data[1].data, recv_data[2]), (2, "Hello 2", None))

  async def test_address(self):
    await self.a.change_addresses([1])
    await self.b.send_to(1, TextData("Hello 1"))

    a_recv = self.a.get_address_receiver([1])
    topic, data = await a_recv.recv()
    self.assertEqual(topic, 1)
    self.assertEqual(data.data, "Hello 1")

  async def test_topic_signal(self):
    await self.b.subscribe([1])
    await asyncio.sleep(0.001)
    async def wait_for_topic_signal():
      await asyncio.wait_for(self.b.wait_for_topic_signal(1), 1)
    receiver_task = asyncio.create_task(wait_for_topic_signal())
    await self.a.send_stream_data(1, TextData("Hello!"))
    await receiver_task

  async def test_fetch(self):
    await self.a.change_addresses([1])
    await self.b.change_addresses([2])

    b_result = None

    async def b_fetch():
      nonlocal b_result
      b_result = await asyncio.wait_for(self.b.fetch(1, "test", "Hello 1"), 1)

    b_fetch_task = asyncio.create_task(b_fetch())

    a_recv = self.a.get_fetch_request_receiver("test")
    req: FetchRequest  = await asyncio.wait_for(a_recv.recv(), 1)
    self.assertEqual(req.body, "Hello 1")
    self.assertEqual(req._return_address, 2)
    await req.respond("Hello 2")
    
    await b_fetch_task
    self.assertEqual(b_result, "Hello 2")

if __name__ == '__main__':
  unittest.main()
