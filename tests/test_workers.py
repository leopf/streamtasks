import unittest
from streamtasks.comm import *
from streamtasks.client import *
from streamtasks.worker import *
from streamtasks.node import *


class TestWorkers(unittest.IsolatedAsyncioTestCase):
  node: LocalNode
  stop_signal: asyncio.Event
  tasks: list[asyncio.Task]
  disposer_task: asyncio.Task
  workers: list[Worker]
  worker: Worker

  async def asyncSetUp(self):
    self.tasks = []
    self.workers = []
    self.node = LocalNode()
    self.worker = Worker(1)
    self.setup_worker(self.worker)

    self.tasks.append(asyncio.create_task(self.node.async_start()))
    self.tasks.append(asyncio.create_task(self.worker.async_start()))

    async def disposer():
      await self.stop_signal.wait()
      self.node.signal_stop()
      for w in self.workers: w.signal_stop()
      for task in self.tasks: await task

    self.disposer_task = asyncio.create_task(disposer())
    self.stop_signal = asyncio.Event()

    await asyncio.sleep(0.001)

  async def asyncTearDown(self):
    self.stop_signal.set()
    await self.disposer_task

  def setup_worker(self, worker: Worker):
    worker.node_conn = self.node.create_connection()
    worker.switch.add_connection(worker.node_conn)
    self.workers.append(worker)

  async def test_basic(self):
    
    pass

if __name__ == '__main__':
  unittest.main()
