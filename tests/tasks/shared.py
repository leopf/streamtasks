import unittest
from streamtasks.client import Client
from streamtasks.comm import Switch, create_local_cross_connector
import asyncio

class TaskTestBase(unittest.IsolatedAsyncioTestCase):
  client: Client
  worker_client: Client
  tasks: list[asyncio.Task]

  async def asyncSetUp(self):
    self.tasks = []

    conn1 = create_local_cross_connector(raw=False)
    conn2 = create_local_cross_connector(raw=True)

    switch = Switch()
    await switch.add_connection(conn1[0])
    await switch.add_connection(conn2[0])
    self.timestamp = 0

    self.client = Client(conn1[1])
    self.worker_client = Client(conn2[1])
    await self.client.change_addresses([1338])
    await asyncio.sleep(0.001)

  async def asyncTearDown(self):
    for task in self.tasks: task.cancel()