import asyncio
import unittest

from streamtasks.utils import AsyncBool, AsyncObservable, AsyncTaskManager


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
    await asyncio.sleep(0)  # let wait_change initialize

    self.assertFalse(task.done())
    obs.test = 1
    await asyncio.sleep(0)
    self.assertTrue(task.done())

  async def test_task_manager(self):
    m = AsyncTaskManager()
    async def routine(): await asyncio.Future()
    t1 = m.create(routine())
    t2 = m.create(routine())
    m.cancel_all()
    await asyncio.wait([ t1, t2 ], timeout=1)
    self.assertTrue(t1.cancelled())
    self.assertTrue(t2.cancelled())


if __name__ == '__main__':
  unittest.main()
