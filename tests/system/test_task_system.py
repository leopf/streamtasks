from typing import Any
import unittest
import httpx
from streamtasks.asgi import ASGIProxyApp
from streamtasks.client.discovery import register_topic_space, wait_for_topic_signal
from streamtasks.net import Link, Switch
from streamtasks.net.message.data import MessagePackData
from streamtasks.services.protocols import AddressNames, WorkerTopics
from streamtasks.system.task import Task, TaskHost, TaskHostRegistrationList, TaskManager, TaskManagerClient, TaskStatus
from streamtasks.system.task_web import TaskWebBackend
from streamtasks.client import Client
from streamtasks.services.discovery import DiscoveryWorker
import asyncio
from tests.shared import async_timeout

class DemoTask(Task):
  def __init__(self, client: Client, stop_event: asyncio.Event): 
    super().__init__(client)
    self.stop_event = stop_event
    self.shoot_topic = self.client.out_topic(1337)
  async def setup(self) -> dict[str, Any]: return { "file:/task-name.txt": "DemoTask" }
  async def run(self):
    self.client.start()
    async with self.shoot_topic, self.shoot_topic.RegisterContext(): await self.stop_event.wait()
  async def shoot(self): await self.shoot_topic.send(MessagePackData("BANG"))

class DemoTaskHost(TaskHost):
  def __init__(self, node_link: Link, switch: Switch | None = None):
    super().__init__(node_link, switch)
    self.stop_event = asyncio.Event()
    self.demo_tasks: list[DemoTask] = []
  @property
  def metadata(self): return { "name": "demo", "file:/task-host-name.txt": "DemoTaskHost" }
  async def create_task(self, config: Any, topic_space_id: int | None) -> Task: 
    task = DemoTask(await self.create_client(topic_space_id), self.stop_event)
    self.demo_tasks.append(task)
    return task

class TestTaskSystem(unittest.IsolatedAsyncioTestCase):
  async def asyncSetUp(self):
    self.tasks: list[asyncio.Task] = []
    self.switch = Switch()
    self.discovery_worker = DiscoveryWorker(await self.switch.add_local_connection())
    self.task_manager = TaskManager(await self.switch.add_local_connection())
    self.task_manager_web = TaskWebBackend(await self.switch.add_local_connection())
    self.demo_task_host = DemoTaskHost(await self.switch.add_local_connection())
    self.client = await self.create_client()
    self.client.start()
    self.tm_client = TaskManagerClient(self.client)
    
    self.tasks.append(asyncio.create_task(self.discovery_worker.run()))
    await wait_for_topic_signal(self.client, WorkerTopics.DISCOVERY_SIGNAL)
    
    self.tasks.append(asyncio.create_task(self.task_manager.run()))
    self.tasks.append(asyncio.create_task(self.task_manager_web.run()))
    self.tasks.append(asyncio.create_task(self.demo_task_host.run()))
    await self.client.request_address()
    self.web_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=ASGIProxyApp(self.client, AddressNames.TASK_MANAGER_WEB)), base_url="http://testserver")
    await self.demo_task_host.ready.wait()

  async def asyncTearDown(self):
    await self.web_client.aclose()
    for task in self.tasks: task.cancel()
    for task in self.tasks: 
      try: await task
      except asyncio.CancelledError: pass
      except: raise
    self.switch.stop_receiving()

  async def create_client(self):
    client = Client(await self.switch.add_local_connection())
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
    task = await self.tm_client.schedule_start_task(reg.id, None)
    self.assertIs(task.status, TaskStatus.running)
    self.assertIsNone(task.error)
    self.assertEqual(len(self.demo_task_host.tasks), 1)
    self.assertIn(task.id, self.demo_task_host.tasks)
    
    updated_task = await self.tm_client.cancel_task_wait(task.id)
    self.assertIs(updated_task.status, TaskStatus.stopped)
    self.assertIsNone(updated_task.error)
    self.assertEqual(updated_task.id, task.id)
      
  @async_timeout(1)
  async def test_topic_spaces(self):
    ts_id, ts_map = await register_topic_space(self.client, {1337})
    self.assertNotEqual(ts_map[1337], 1337)
    reg = await self.demo_task_host.register(AddressNames.TASK_MANAGER)
    task = await self.tm_client.schedule_start_task(reg.id, None, ts_id)

    recv_topic = self.client.in_topic(ts_map[1337])
    async with recv_topic, recv_topic.RegisterContext():
      for running_task in self.demo_task_host.demo_tasks:
        await running_task.shoot_topic.wait_requested()
        await running_task.shoot()
      data = await recv_topic.recv_data()
      self.assertEqual(data.data, "BANG")
    
    await self.tm_client.cancel_task_wait(task.id)
    
  @async_timeout(1)
  async def test_start_shutdown(self):
    reg = await self.demo_task_host.register(AddressNames.TASK_MANAGER)
    task = await self.tm_client.schedule_start_task(reg.id, None)
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
      
  async def test_web_api(self):
    reg = await self.demo_task_host.register(AddressNames.TASK_MANAGER)
    task = await self.tm_client.schedule_start_task(reg.id, None)

    registered_task_hosts = TaskHostRegistrationList.validate_json((await self.web_client.get("/api/task-hosts")).text)
    self.assertEqual(len(registered_task_hosts), 1)
    self.assertEqual(registered_task_hosts[0].id, reg.id)
    
    self.assertEqual((await self.web_client.get(f"/task-host/{reg.id}/task-host-name.txt")).text, "DemoTaskHost")
    self.assertEqual((await self.web_client.get(f"/task/{task.id}/task-name.txt")).text, "DemoTask")
    
    stopped_task = await self.tm_client.cancel_task_wait(task.id)
    self.assertEqual(stopped_task.id, task.id)
    self.assertEqual(stopped_task.status, TaskStatus.stopped)

if __name__ == '__main__':
  unittest.main()
