import unittest
from streamtasks.comm import *
from streamtasks.client import *
from streamtasks.asgi import *
from streamtasks.worker import *
from streamtasks.node import *
import asyncio
from uuid import uuid4
from fastapi import FastAPI
import httpx

class TestASGI(unittest.IsolatedAsyncioTestCase):
  client1: Client
  client2: Client

  tasks: list[asyncio.Task]

  async def asyncSetUp(self):
    self.tasks = []

    conn1 = create_local_cross_connector(raw=False)
    conn2 = create_local_cross_connector(raw=False)

    switch = Switch()
    await switch.add_connection(conn1[0])
    await switch.add_connection(conn2[0])

    self.client1 = Client(conn1[1])
    self.client2 = Client(conn2[1])
    await self.client1.change_addresses([1338])
    await self.client2.change_addresses([1337])
    await asyncio.sleep(0.001)

  async def asyncTearDown(self):
    for task in self.tasks: task.cancel()

  async def setup_worker(self, worker: Worker):
    await worker.set_node_connection(await self.node.create_connection(raw=True))
    self.tasks.append(asyncio.create_task(worker.start()))

  async def test_transmit(self):
    sender = ASGIEventSender(self.client1, 1337, 1)
    receiver = ASGIEventReceiver(self.client2, 1337)

    await receiver.start_recv()

    await sender.send({"type": "test", "data": "test"})
    data = await receiver.recv()
    self.assertEqual([{"type": "test", "data": "test"}], data.events)

    await sender.close()
    data = await receiver.recv()
    self.assertEqual([], data.events)
    self.assertEqual(True, data.closed)

  async def test_app_fastapi(self):
    demo_app = FastAPI()
    demo_app.add_api_route("/", lambda: { "text": "Hello from FastAPI!" })

    runner = ASGIAppRunner(self.client2, demo_app, "demo_app", 1337)
    self.tasks.append(asyncio.create_task(runner.start()))

    proxy_app = ASGIProxyApp(self.client1, 1337, "demo_app", 1338)
    
    transport = httpx.ASGITransport(app=proxy_app)
    client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    response = await client.get("/")
    self.assertEqual(200, response.status_code)
    self.assertEqual(b'{"text":"Hello from FastAPI!"}', response.content)

  async def test_app(self):
    async def demo_app(scope, receive, send):
      await send({"type": "http.response.start", "status": 200})
      await send({"type": "http.response.body", "body": b"Hello world!"})

    runner = ASGIAppRunner(self.client2, demo_app, "demo_app", 1337)
    self.tasks.append(asyncio.create_task(runner.start()))

    proxy_app = ASGIProxyApp(self.client1, 1337, "demo_app", 1338)
    
    transport = httpx.ASGITransport(app=proxy_app)
    client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    response = await client.get("/")
    self.assertEqual(200, response.status_code)
    self.assertEqual(b"Hello world!", response.content)
    

if __name__ == '__main__':
  unittest.main()
