import asyncio
import os
import tempfile
import unittest
from streamtasks.client import Client
from streamtasks.client.receiver import AddressReceiver
from streamtasks.connection import connect, create_server
from streamtasks.net import ConnectionClosedError, Switch
from streamtasks.net.serialization import RawData
from streamtasks.message.types import TextMessage
from tests.shared import async_timeout


class TestConnection(unittest.IsolatedAsyncioTestCase):
  topic_count = 3
  message_count = 100

  async def asyncSetUp(self):
    self.switch = Switch()
    self.tasks: list[asyncio.Task] = []

    self.client = Client(await self.switch.add_local_connection())
    self.client.start()
    await self.client.set_address(1)

  async def asyncTearDown(self):
    for task in self.tasks: task.cancel()
    for task in self.tasks:
      try: await task
      except (asyncio.CancelledError, ConnectionClosedError): pass
      except: raise

  @async_timeout(2)
  async def test_unix_connection(self):
    sock_path = tempfile.mktemp(".sock")
    unix_url = "unix://" + sock_path

    server = create_server(unix_url)
    await self.switch.add_link(await server.create_link())
    self.tasks.append(asyncio.create_task(server.run()))

    async with AddressReceiver(self.client, 1, 1) as recv:
      await server.wait_running()
      client2 = Client(await connect(unix_url))
      client2.start()
      while server.connection_count != 1: await server.wait_connections_changed()
      await asyncio.sleep(0.001) # ?? wait for address to be registered in link
      await client2.send_to((1, 1), RawData(TextMessage(timestamp=1, value="Hello").model_dump()))

      _, data = await recv.recv()
      self.assertEqual(data.data["value"], "Hello")

      client2._link.close()
      while server.connection_count != 0: await server.wait_connections_changed()

    if os.path.exists(sock_path): os.unlink(sock_path)

class TestConnectionAuth(unittest.IsolatedAsyncioTestCase):
  async def asyncSetUp(self):
    self.auth_token = "ABC"
    self.switch = Switch()
    self.unix_path = tempfile.mktemp(".sock")
    self.server = create_server(self.get_unix_url(self.auth_token))
    self.tasks = []
    await self.switch.add_link(await self.server.create_link())
    self.tasks.append(asyncio.create_task(self.server.run()))

  async def asyncTearDown(self):
    for task in self.tasks:
      task.cancel()
      try: await task
      except asyncio.CancelledError: pass
    if os.path.exists(self.unix_path): os.unlink(self.unix_path)

  def get_unix_url(self, auth): return f"unix://{self.unix_path}?auth={auth}"

  async def test_auth(self):
    await connect(self.get_unix_url(self.auth_token))
    with self.assertRaises(ConnectionError): await connect(self.get_unix_url("123"))

if __name__ == '__main__':
  unittest.main()
