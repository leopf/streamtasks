import asyncio
import os
import tempfile
import unittest
from streamtasks.client import Client
from streamtasks.client.receiver import AddressReceiver
from streamtasks.connection import UnixSocketServer, connect_unix_socket
from streamtasks.net import ConnectionClosedError, create_queue_connection
from streamtasks.net.message.data import RawData
from streamtasks.message import TextMessage


class TestSync(unittest.IsolatedAsyncioTestCase):
  topic_count = 3
  message_count = 100

  async def asyncSetUp(self):
    self.tasks: list[asyncio.Task] = []
    conn = create_queue_connection()

    self.client = Client(conn[0])
    self.client.start()
    await self.client.set_address(1)
    self.link = conn[1]

  async def asyncTearDown(self):
    for task in self.tasks: task.cancel()
    for task in self.tasks:
      try: await task
      except (asyncio.CancelledError, ConnectionClosedError): pass
      except: raise

  async def test_unix_connection(self):
    sock_path = tempfile.mktemp(".sock")
    server = UnixSocketServer(self.link ,sock_path)
    self.tasks.append(asyncio.create_task(server.run()))

    async with AddressReceiver(self.client, 1, 1) as recv:
      await server.wait_running()
      client2 = Client(await connect_unix_socket(sock_path))
      client2.start()
      while server.connection_count != 1: await server.wait_connections_changed()
      await asyncio.sleep(0.001) # ?? wait for address to be registered in link
      await client2.send_to((1, 1), RawData(TextMessage(timestamp=1, value="Hello").model_dump()))

      _, data = await recv.recv()
      self.assertEqual(data.data["value"], "Hello")

      client2._link.close()
      while server.connection_count != 0: await server.wait_connections_changed()


    if os.path.exists(sock_path): os.unlink(sock_path)

if __name__ == '__main__':
  unittest.main()
