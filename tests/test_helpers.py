import asyncio
import unittest

from streamtasks.helpers import AsyncBool, AsyncObservable

class TestHelpers(unittest.IsolatedAsyncioTestCase):
  async def test_async_bool(self):
    b = AsyncBool(False)
    self.assertFalse(b.value)
    
    task = asyncio.create_task(b.wait(True))
    await asyncio.sleep(0) # let b.wait initialize

    self.assertFalse(task.done())
    b.set(True)
    self.assertTrue(b.value)
    await asyncio.sleep(0)
    self.assertTrue(task.done())

  async def test_async_observer(self):
    obs = AsyncObservable()
    
    task = asyncio.create_task(obs.wait_change())
    await asyncio.sleep(0) # let wait_change initialize

    self.assertFalse(task.done())
    obs.test = 1
    await asyncio.sleep(0)
    self.assertTrue(task.done())

if __name__ == '__main__':
  unittest.main()