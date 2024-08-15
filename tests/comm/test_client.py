from typing import Any
import unittest
import asyncio
from streamtasks.client import Client
from streamtasks.client.broadcast import BroadcastReceiver, BroadcastingServer
from streamtasks.client.discovery import wait_for_topic_signal
from streamtasks.client.fetch import FetchRequest, FetchRequestReceiver
from streamtasks.client.receiver import AddressReceiver, TopicsReceiver
from streamtasks.client.signal import SignalRequestReceiver, SignalServer, send_signal
from streamtasks.net.serialization import RawData
from streamtasks.net import ConnectionClosedError, Switch, create_queue_connection
from streamtasks.services.discovery import DiscoveryWorker
from streamtasks.services.protocols import WorkerPorts, WorkerTopics
from tests.shared import async_timeout


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
    for task in self.tasks: task.cancel()
    for task in self.tasks:
      try: await task
      except (asyncio.CancelledError, ConnectionClosedError): pass
      except: raise
    self.switch.stop_receiving()

  @async_timeout(1)
  async def test_subscribe(self):
    sub_topic = self.a.out_topic(1)
    await sub_topic.start()
    await sub_topic.set_registered(True)
    self.assertFalse(sub_topic.is_requested)
    await self.b.register_in_topics([ 1 ])
    await sub_topic.wait_requested(True)
    self.assertTrue(sub_topic.is_requested)

  @async_timeout(1)
  async def test_provide_subscribe(self):
    await self.a.register_out_topics([ 1, 2 ])

    async with TopicsReceiver(self.b, [ 1, 2 ]) as b_recv:
      await self.a.send_stream_data(1, RawData("Hello 1"))
      await self.a.send_stream_data(2, RawData("Hello 2"))

      recv_data = await b_recv.get()
      self.assertEqual((recv_data[0], recv_data[1].data), (1, "Hello 1"))

      recv_data = await b_recv.get()
      self.assertEqual((recv_data[0], recv_data[1].data), (2, "Hello 2"))

      await self.b.unregister_in_topics([ 1 ])

      await self.a.send_stream_data(1, RawData("Hello 1"))
      await self.a.send_stream_data(2, RawData("Hello 2"))

      recv_data = await b_recv.get()
      self.assertEqual((recv_data[0], recv_data[1].data), (2, "Hello 2"))

  @async_timeout(1)
  async def test_address(self):
    await self.a.set_address(1)
    await self.b.send_to((1, 10), RawData("Hello 1"))

    a_recv = AddressReceiver(self.a, 1, 10)
    topic, data = await a_recv.recv()
    self.assertEqual(topic, 1)
    self.assertEqual(data.data, "Hello 1")

  @async_timeout(1)
  async def test_topic_signal(self):
    await self.b.register_in_topics([1])
    await asyncio.sleep(0.001)

    async def wait_topic():
      await wait_for_topic_signal(self.b, 1)
    receiver_task = asyncio.create_task(wait_topic())
    await self.a.send_stream_data(1, RawData("Hello!"))
    await receiver_task

  @async_timeout(1)
  async def test_fetch(self):
    await self.a.set_address(1)
    await self.b.set_address(2)

    b_result = None

    async def b_fetch():
      nonlocal b_result
      b_result = await self.b.fetch(1, "test", "Hello 1")

    async with FetchRequestReceiver(self.a, "test") as a_recv:
      b_fetch_task = asyncio.create_task(b_fetch())
      req: FetchRequest = await a_recv.get()
      self.assertEqual(req.body, "Hello 1")
      self.assertEqual(req._return_endpoint, (2, WorkerPorts.DYNAMIC_START))
      await req.respond("Hello 2")

    await b_fetch_task
    self.assertEqual(b_result, "Hello 2")

  @async_timeout(1)
  async def test_signal(self):
    await self.a.set_address(1)
    async with SignalRequestReceiver(self.a, "test") as a_recv:
      self.tasks.append(asyncio.create_task(send_signal(self.b, self.a.address, "test", "Hello 1")))
      data: Any = await a_recv.get()
      self.assertEqual(data, "Hello 1")

  @async_timeout(1000)
  async def test_signal_server(self):
    await self.a.set_address(1)
    event_test1, event_test2 = asyncio.Event(), asyncio.Event()
    signal_server = SignalServer(self.a)
    received = None
    @signal_server.route("test1")
    def _(data: str):
      nonlocal received
      received = data
      event_test1.set()

    @signal_server.route("test2")
    def _(data: str):
      nonlocal received
      received = data
      event_test2.set()

    self.tasks.append(asyncio.create_task(signal_server.run()))
    await send_signal(self.b, self.a.address, "test1", "hello1")
    await event_test1.wait()
    self.assertEqual(received, "hello1")
    await send_signal(self.b, self.a.address, "test2", "hello2")
    await event_test2.wait()
    self.assertEqual(received, "hello2")


  @async_timeout(1)
  async def test_broadcast(self):
    discovery_worker = DiscoveryWorker()
    await self.switch.add_link(await discovery_worker.create_link())
    self.tasks.append(asyncio.create_task(discovery_worker.run()))

    await self.a.set_address(100)
    await self.b.set_address(101)

    await wait_for_topic_signal(self.a, WorkerTopics.DISCOVERY_SIGNAL)
    await self.a.request_topic_ids(1)

    server = BroadcastingServer(self.a)
    self.tasks.append(asyncio.create_task(server.run()))

    receiver = BroadcastReceiver(self.b, [ "test/1" ], self.a.address)

    await server.broadcast("test/1", RawData("Hello1"))
    await server.broadcast("test/2", RawData("Hello2"))
    await receiver.start_recv()
    await server.broadcast("test/1", RawData("Hello1"))
    await server.broadcast("test/2", RawData("Hello2"))
    ns, data = await receiver.get()
    self.assertEqual(ns, "test/1")
    self.assertEqual(data.data, "Hello1")
    await receiver.stop_recv()
    await server.broadcast("test/1", RawData("Hello1"))
    await server.broadcast("test/2", RawData("Hello2"))
    await asyncio.sleep(0)
    self.assertTrue(receiver.empty())

if __name__ == '__main__':
  unittest.main()
