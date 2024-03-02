import unittest
import asyncio
from fastapi import FastAPI
import httpx
from streamtasks.asgi import ASGIAppRunner, ASGIEventReceiver, ASGIEventSender, ASGIProxyApp
from streamtasks.client import Client
from pydantic import BaseModel

from streamtasks.net import Switch, create_queue_connection


class TestModel(BaseModel):
  test: str


def get_client_for_app(app):
  transport = httpx.ASGITransport(app=app)
  return httpx.AsyncClient(transport=transport, base_url="http://testserver")


class TestASGI(unittest.IsolatedAsyncioTestCase):
  client1: Client
  client2: Client

  tasks: list[asyncio.Task]

  async def asyncSetUp(self):
    self.tasks = []

    conn1 = create_queue_connection(raw=False)
    conn2 = create_queue_connection(raw=False)

    switch = Switch()
    await switch.add_link(conn1[0])
    await switch.add_link(conn2[0])

    self.client1 = Client(conn1[1])
    self.client1.start()
    self.client2 = Client(conn2[1])
    self.client2.start()
    await self.client1.set_address(1338)
    await self.client2.set_address(1337)
    await asyncio.sleep(0.001)

  async def asyncTearDown(self):
    for task in self.tasks: task.cancel()

  async def test_transmit(self):
    sender = ASGIEventSender(self.client1, (1337, 101))
    receiver = ASGIEventReceiver(self.client2, 1337, 101)

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

    @demo_app.get("/")
    def basid_ep(): return { "text": "Hello from FastAPI!" }

    @demo_app.post("/post")
    async def post(data: TestModel):
      return { "data": data }

    runner = ASGIAppRunner(self.client2, demo_app)
    self.tasks.append(asyncio.create_task(runner.run()))

    proxy_app = ASGIProxyApp(self.client1, 1337)

    client = get_client_for_app(proxy_app)
    response = await client.get("/")
    self.assertEqual(200, response.status_code)
    self.assertEqual(b'{"text":"Hello from FastAPI!"}', response.content)

    response = await client.post("/post", json={"test": "test"})
    self.assertEqual(200, response.status_code)
    self.assertEqual(b'{"data":{"test":"test"}}', response.content)
    await client.aclose()

  async def test_app(self):
    async def demo_app(scope, receive, send):
      await send({"type": "http.response.start", "status": 200})
      await send({"type": "http.response.body", "body": b"Hello world!"})

    runner = ASGIAppRunner(self.client2, demo_app)
    self.tasks.append(asyncio.create_task(runner.run()))

    proxy_app = ASGIProxyApp(self.client1, 1337)

    client = get_client_for_app(proxy_app)
    response = await client.get("/")
    self.assertEqual(200, response.status_code)
    self.assertEqual(b"Hello world!", response.content)
    await client.aclose()


if __name__ == '__main__':
  unittest.main()
