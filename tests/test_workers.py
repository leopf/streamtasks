import unittest
from streamtasks.comm import *
from streamtasks.client import *
from streamtasks.worker import *
from streamtasks.node import *


class TestWorkers(unittest.IsolatedAsyncioTestCase):
  node: LocalNode
  worker: Worker


  stop_signal: asyncio.Event
  tasks: list[asyncio.Task]

  async def asyncSetUp(self):
    self.stop_signal = asyncio.Event()
    self.tasks = []
    self.node = LocalNode()

    self.worker = Worker(1)
    self.setup_worker(self.worker)

    self.tasks.append(asyncio.create_task(self.node.async_start(self.stop_signal)))
    self.tasks.append(asyncio.create_task(self.worker.async_start(self.stop_signal)))

    await asyncio.sleep(0.001)

  async def asyncTearDown(self):
    self.stop_signal.set()
    for task in self.tasks: await task

  def setup_worker(self, worker: Worker):
    worker.set_node_connection(self.node.create_connection())
    self.tasks.append(asyncio.create_task(worker.async_start(self.stop_signal)))

  async def test_basic(self):
    discovery_worker = DiscoveryWorker(1)
    self.setup_worker(discovery_worker)

    client = Client(self.worker.create_connection())
    address = await client.request_address(1)
    
    self.assertEqual(WorkerAddresses.COUNTER_INIT, address)

if __name__ == '__main__':
  unittest.main()
