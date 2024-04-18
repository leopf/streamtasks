import asyncio
import unittest

from streamtasks.utils import AsyncBool, AsyncMPProducer, AsyncObservable, AsyncProducer, AsyncTaskManager
from tests.shared import async_timeout


class TestUtils(unittest.IsolatedAsyncioTestCase):
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

class DemoProducer(AsyncProducer):
  def __init__(self) -> None:
    super().__init__()
    self.running = AsyncBool(False)
  
  async def run(self):
    try:
      self.running.set(True)
      await asyncio.Future()
    finally: self.running.set(False)

class DemoProducerMP(AsyncMPProducer):
  def __init__(self) -> None:
    super().__init__()
    self.running = AsyncBool(False)
  
  async def run(self):
    try:
      self.running.set(True)
      await super().run()
    finally: self.running.set(False)

  def run_sync(self): self.stop_event.wait()

class TestProducer(unittest.IsolatedAsyncioTestCase):
  def setUp(self) -> None:
    self.producer = DemoProducer()

  @async_timeout(1)
  async def test_flow_double_enter_exit(self):
    await self.producer.running.wait(False)
    await self.producer.__aenter__()
    await self.producer.running.wait(True)
    await self.producer.__aenter__()
    await self.producer.running.wait(True)
    await self.producer.__aexit__()
    await self.producer.running.wait(True)
    await self.producer.__aexit__()
    await self.producer.running.wait(False)

  @async_timeout(1)
  async def test_flow_double_exit(self):
    await self.producer.running.wait(False)
    await self.producer.__aenter__()
    await self.producer.running.wait(True)
    await self.producer.__aexit__()
    await self.producer.running.wait(False)
    await self.producer.__aexit__()
    await self.producer.running.wait(False)
    
  @async_timeout(1)
  async def test_flow_double_exit_sim(self):
    await self.producer.running.wait(False)
    await self.producer.__aenter__()
    await self.producer.running.wait(True)
    await asyncio.wait([
      asyncio.create_task(self.producer.__aexit__()),
      asyncio.create_task(self.producer.__aexit__()),
    ])
    await self.producer.running.wait(False)
    
  @async_timeout(1)
  async def test_await_after(self):
    futs = [
      self.producer.__aenter__(),
      self.producer.__aexit__()
    ]
    
    for f in futs: await f
    self.assertFalse(self.producer.running)

class TestProducerMP(TestProducer):
  def setUp(self) -> None:
    self.producer = DemoProducerMP()

if __name__ == '__main__':
  unittest.main()
