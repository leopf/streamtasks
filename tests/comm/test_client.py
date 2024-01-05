import unittest
import asyncio
from streamtasks.client import Client
from streamtasks.client.discovery import wait_for_topic_signal
from streamtasks.client.fetch import FetchRequest, FetchRequestReceiver
from streamtasks.client.receiver import AddressReceiver, TopicsReceiver
from streamtasks.message.data import TextData
from streamtasks.net import Switch, create_queue_connection
from streamtasks.system.protocols import WorkerPorts


class TestClient(unittest.IsolatedAsyncioTestCase):
  a: Client
  b: Client
  tasks: list[asyncio.Task]

  async def asyncSetUp(self):
    conn1 = create_queue_connection(raw=False)
    conn2 = create_queue_connection(raw=True)

    self.switch = Switch()
    await self.switch.add_link(conn1[0])
    await self.switch.add_link(conn2[0])

    self.tasks = []

    self.a = Client(conn1[1])
    self.a.start()
    self.b = Client(conn2[1])
    self.b.start()
    await asyncio.sleep(0.001)

  async def asyncTearDown(self):
    self.switch.stop_receiving()
    for task in self.tasks: task.cancel()

  async def test_subscribe(self):
    sub_topic = self.a.out_topic(1)
    await sub_topic.start()
    await sub_topic.set_registered(True)
    self.assertFalse(sub_topic.is_requested)
    await self.b.register_in_topics([ 1 ])
    await asyncio.wait_for(sub_topic.wait_requested(True), 1)
    self.assertTrue(sub_topic.is_requested)

  async def test_provide_subscribe(self):
    await self.a.register_out_topics([ 1, 2 ])

    async with TopicsReceiver(self.b, [ 1, 2 ]) as b_recv:
      await self.a.send_stream_data(1, TextData("Hello 1"))
      await self.a.send_stream_data(2, TextData("Hello 2"))

      recv_data = await asyncio.wait_for(b_recv.recv(), 1)
      self.assertEqual((recv_data[0], recv_data[1].data, recv_data[2]), (1, "Hello 1", None))

      recv_data = await asyncio.wait_for(b_recv.recv(), 1)
      self.assertEqual((recv_data[0], recv_data[1].data, recv_data[2]), (2, "Hello 2", None))

      await self.b.unregister_in_topics([ 1 ])

      await self.a.send_stream_data(1, TextData("Hello 1"))
      await self.a.send_stream_data(2, TextData("Hello 2"))

      recv_data = await asyncio.wait_for(b_recv.recv(), 1)
      self.assertEqual((recv_data[0], recv_data[1].data, recv_data[2]), (2, "Hello 2", None))

  async def test_address(self):
    await self.a.set_address(1)
    await self.b.send_to((1, 10), TextData("Hello 1"))

    a_recv = AddressReceiver(self.a, 1, 10)
    topic, data = await asyncio.wait_for(a_recv.recv(), 1)
    self.assertEqual(topic, 1)
    self.assertEqual(data.data, "Hello 1")

  async def test_topic_signal(self):
    await self.b.register_in_topics([1])
    await asyncio.sleep(0.001)

    async def wait_topic():
      await asyncio.wait_for(wait_for_topic_signal(self.b, 1), 1)
    receiver_task = asyncio.create_task(wait_topic())
    await self.a.send_stream_data(1, TextData("Hello!"))
    await receiver_task

  async def test_fetch(self):
    await self.a.set_address(1)
    await self.b.set_address(2)

    b_result = None

    async def b_fetch():
      nonlocal b_result
      b_result = await asyncio.wait_for(self.b.fetch(1, "test", "Hello 1"), 1)

    async with FetchRequestReceiver(self.a, "test") as a_recv:
      b_fetch_task = asyncio.create_task(b_fetch())
      req: FetchRequest = await asyncio.wait_for(a_recv.recv(), 1)
      self.assertEqual(req.body, "Hello 1")
      self.assertEqual(req._return_endpoint, (2, WorkerPorts.DYNAMIC_START))
      await req.respond("Hello 2")

    await b_fetch_task
    self.assertEqual(b_result, "Hello 2")


if __name__ == '__main__':
  unittest.main()
