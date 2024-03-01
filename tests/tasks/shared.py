import unittest
from streamtasks.client import Client
from streamtasks.net import Switch, create_queue_connection
import asyncio
from streamtasks.system.task import Task


async def start_task(task: Task):
  await task.setup()
  await task.run()


class TaskTestBase(unittest.IsolatedAsyncioTestCase):
  client: Client
  worker_client: Client
  tasks: list[asyncio.Task]

  async def asyncSetUp(self):
    self.tasks = []

    conn1 = create_queue_connection(raw=False)
    conn2 = create_queue_connection(raw=True)

    switch = Switch()
    await switch.add_link(conn1[0])
    await switch.add_link(conn2[0])
    self.timestamp = 0

    self.client = Client(conn1[1])
    self.worker_client = Client(conn2[1])
    await asyncio.sleep(0.001)

  async def asyncTearDown(self):
    for task in self.tasks:
      if task.done(): await task
      else: task.cancel()