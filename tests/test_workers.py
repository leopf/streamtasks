import unittest
from streamtasks.comm import *
from streamtasks.client import *
from streamtasks.worker import *
from streamtasks.node import *


class TestWorkers(unittest.IsolatedAsyncioTestCase):
  node: LocalNode
  stop_signal: asyncio.Event
  tasks: list[asyncio.Task]

  async def asyncSetUp(self):
    self.node = LocalNode()
    self.worker = Worker(1)
    self.worker.node_conn = self.node.create_connection() # hack to prevent remote connections

    tasks = [ asyncio.create_task(a) for a in [
      self.node.async_start(),
      self.worker.async_start(),
    ]]

    async def disposer():
      await self.stop_signal.wait()
      self.node.signal_stop()
      self.worker.signal_stop()
      for task in tasks: await task

    self.tasks = [asyncio.create_task(disposer())]
    self.stop_signal = asyncio.Event()

    await asyncio.sleep(0.001)

  async def asyncTearDown(self):
    self.stop_signal.set()
    for task in self.tasks: await task

  async def test_basic(self):
    
    pass

if __name__ == '__main__':
  unittest.main()
