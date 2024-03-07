from typing import Any
import unittest
from streamtasks.client.discovery import wait_for_topic_signal
from streamtasks.net import Link, Switch, create_queue_connection
from streamtasks.services.protocols import AddressNames, WorkerTopics
from streamtasks.system.task import Task, TaskHost, TaskManager, TaskManagerClient, TaskStatus
from streamtasks.client import Client
from streamtasks.services.discovery import DiscoveryWorker
import asyncio
from tests.shared import async_timeout

class DemoTask(Task):
  def __init__(self, client: Client, stop_event: asyncio.Event): 
    super().__init__(client)
    self.stop_event = stop_event
  async def run(self): await self.stop_event.wait()

class DemoTaskHost(TaskHost):
  def __init__(self, node_link: Link, switch: Switch | None = None):
    super().__init__(node_link, switch)
    self.stop_event = asyncio.Event()
  @property
  def metadata(self): return { "name": "demo" }
  async def create_task(self, config: Any) -> Task: return DemoTask(await self.create_client(), self.stop_event)

class TestTaskSystem(unittest.IsolatedAsyncioTestCase):
  async def asyncSetUp(self):
    self.tasks: list[asyncio.Task] = []
    self.switch = Switch()
    self.discovery_worker = DiscoveryWorker(await self.create_link())
    self.task_manager = TaskManager(await self.create_link())
    self.demo_task_host = DemoTaskHost(await self.create_link())
    self.client = await self.create_client()
    self.client.start()
    self.tm_client = TaskManagerClient(self.client)
    
    self.tasks.append(asyncio.create_task(self.discovery_worker.run()))
    await wait_for_topic_signal(self.client, WorkerTopics.DISCOVERY_SIGNAL)
    
    self.tasks.append(asyncio.create_task(self.task_manager.run()))
    self.tasks.append(asyncio.create_task(self.demo_task_host.run()))
    await self.client.request_address()
    await self.demo_task_host.ready.wait()

  async def asyncTearDown(self):
    self.switch.stop_receiving()
    for task in self.tasks: task.cancel()
    for task in self.tasks: 
      try: await task
      except asyncio.CancelledError: pass
      except: raise

  async def create_link(self):
    conn = create_queue_connection()
    await self.switch.add_link(conn[0])
    return conn[1]
  
  async def create_client(self):
    client = Client(await self.create_link())
    client.start()
    return client

  @async_timeout(1)
  async def test_registration(self):
    reg = await self.demo_task_host.register(AddressNames.TASK_MANAGER)
    task_hosts = await self.tm_client.list_task_hosts()
    self.assertEqual(len(task_hosts), 1)
    for k, v in self.demo_task_host.metadata.items(): self.assertEqual(task_hosts[0].metadata[k], v)
    await self.demo_task_host.unregister(AddressNames.TASK_MANAGER, reg.id)
    await asyncio.sleep(0.001) # HACK: we dont want sleeps
    task_hosts = await self.tm_client.list_task_hosts()
    self.assertEqual(len(task_hosts), 0)

  @async_timeout(1)
  async def test_start_cancel(self):
    reg = await self.demo_task_host.register(AddressNames.TASK_MANAGER)
    task = await self.tm_client.start_task(reg.id, None)
    self.assertIs(task.status, TaskStatus.running)
    self.assertIsNone(task.error)
    self.assertEqual(len(self.demo_task_host.tasks), 1)
    self.assertIn(task.id, self.demo_task_host.tasks)
    
    updated_task = await self.tm_client.cancel_task_wait(task.id)
    self.assertIs(updated_task.status, TaskStatus.stopped)
    self.assertIsNone(updated_task.error)
    self.assertEqual(updated_task.id, task.id)
      
  @async_timeout(1)
  async def test_start_shutdown(self):
    reg = await self.demo_task_host.register(AddressNames.TASK_MANAGER)
    task = await self.tm_client.start_task(reg.id, None)
    self.assertIs(task.status, TaskStatus.running)
    self.assertIsNone(task.error)
    self.assertEqual(len(self.demo_task_host.tasks), 1)
    self.assertIn(task.id, self.demo_task_host.tasks)
    
    async with self.tm_client.task_message_receiver([ task.id ]) as receiver:
      self.demo_task_host.stop_event.set()
      updated_task = await receiver.get()
      self.assertIs(updated_task.status, TaskStatus.ended)
      self.assertIsNone(updated_task.error)
      self.assertEqual(updated_task.id, task.id)

if __name__ == '__main__':
  unittest.main()
