import unittest
from streamtasks.comm import *
from streamtasks.client import *
from streamtasks.client.asgi import *
from streamtasks.worker import *
from streamtasks.node import *
import asyncio
from uuid import uuid4
import httpx

class TestASGI(unittest.IsolatedAsyncioTestCase):
  client1: Client
  client2: Client

  stop_signal: asyncio.Event
  tasks: list[asyncio.Task]

  async def asyncSetUp(self):
    self.stop_signal = asyncio.Event()
    self.tasks = []

    conn1 = create_local_cross_connector(raw=False)
    conn2 = create_local_cross_connector(raw=False)

    switch = Switch()
    await switch.add_connection(conn1[0])
    await switch.add_connection(conn2[0])

    self.tasks.append(create_switch_processing_task(switch, self.stop_signal))

    self.client1 = Client(conn1[1])
    self.client2 = Client(conn2[1])
    await self.client1.change_addresses([1338])
    await self.client2.change_addresses([1337])
    await asyncio.sleep(0.001)

  async def asyncTearDown(self):
    self.stop_signal.set()
    for task in self.tasks: await task

  async def setup_worker(self, worker: Worker):
    await worker.set_node_connection(await self.node.create_connection(raw=True))
    self.tasks.append(asyncio.create_task(worker.async_start(self.stop_signal)))

  async def test_transmit(self):
    sender = ASGIEventSender(self.client1, 1337, 1)
    receiver = ASGIEventReceiver(self.client2, 1337)

    receiver.start_recv()

    await sender.send({"type": "test", "data": "test"})
    data = await receiver.recv()
    self.assertEqual([{"type": "test", "data": "test"}], data.events)

    await sender.close()
    data = await receiver.recv()
    self.assertEqual([], data.events)
    self.assertEqual(True, data.closed)

  async def test_half_app(self):
    async def demo_app(scope, receive, send):
      await send({"type": "http.response.start", "status": 200})
      await send({"type": "http.response.body", "body": b"Hello world!"})

    runner = ASGIAppRunner(self.client2, demo_app, "demo_app", 1337)
    self.tasks.append(asyncio.create_task(runner.async_start(self.stop_signal)))

    async def proxy_app(scope, receive, send):
      connection_id = str(uuid4())
      closed_signal = asyncio.Event()

      await self.client1.fetch(1337, "demo_app", ASGIInitMessage(
        scope=JSONValueTransformer.annotate_value(scope), 
        connection_id=connection_id, 
        return_address=1338))
      
      async def send_loop():
        sender = ASGIEventSender(self.client1, 1337, connection_id)
        while not closed_signal.is_set():
          event = await receive()
          await sender.send(event)
          await asyncio.sleep(0.001)

      async def recv_loop():
        receiver = ASGIEventReceiver(self.client1, 1338)
        with receiver:
          while True:
            data = await receiver.recv()
            for event in data.events:
              await send(MessagePackValueTransformer.deannotate_value(event))
            if data.closed: break
        closed_signal.set()

      recv_loop_task = asyncio.create_task(recv_loop())
      send_loop_task = asyncio.create_task(send_loop())
      await closed_signal.wait()
      send_loop_task.cancel()
      recv_loop_task.cancel()

    transport = httpx.ASGITransport(app=proxy_app)
    client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    response = await client.get("/")
    self.assertEqual(200, response.status_code)
    self.assertEqual(b"Hello world!", response.content)

  async def test_app(self):
    async def demo_app(scope, receive, send):
      await send({"type": "http.response.start", "status": 200})
      await send({"type": "http.response.body", "body": b"Hello world!"})

    runner = ASGIAppRunner(self.client2, demo_app, "demo_app", 1337)
    self.tasks.append(asyncio.create_task(runner.async_start(self.stop_signal)))

    proxy_app = ASGIProxyApp(self.client1, 1337, "demo_app", 1338)
    
    transport = httpx.ASGITransport(app=proxy_app)
    client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    response = await client.get("/")
    self.assertEqual(200, response.status_code)
    self.assertEqual(b"Hello world!", response.content)
    

if __name__ == '__main__':
  unittest.main()
