from typing import Any
import unittest
import httpx
from streamtasks.asgi import ASGIProxyApp
from streamtasks.client.discovery import register_topic_space, wait_for_topic_signal
from streamtasks.client.fetch import FetchError
from streamtasks.net import ConnectionClosedError, Switch
from streamtasks.net.serialization import RawData
from streamtasks.services.constants import NetworkAddressNames, NetworkTopics
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
  async def shoot(self): await self.shoot_topic.send(RawData("BANG"))

class DemoTaskHost(TaskHost):
  def __init__(self):
    super().__init__()
    self.stop_event = asyncio.Event()
    self.demo_tasks: list[DemoTask] = []
  @property
  def metadata(self): return { "name": "demo", "file:/task-host-name.txt": "DemoTaskHost" }
  async def create_task(self, config: Any, topic_space_id: int | None) -> Task:
    task = DemoTask(await self.create_client(topic_space_id), self.stop_event)
    self.demo_tasks.append(task)
    return task

class TestTaskSystem(unittest.IsolatedAsyncioTestCase):
  lock = asyncio.Lock()

  async def asyncSetUp(self):
    await TestTaskSystem.lock.acquire()
    self.tasks: list[asyncio.Task] = []
    self.switch = Switch()
    self.discovery_worker = DiscoveryWorker()
    self.task_manager = TaskManager()
    self.task_manager_web = TaskWebBackend()
    self.demo_task_host = DemoTaskHost()

    await self.switch.add_link(await self.discovery_worker.create_link())
    await self.switch.add_link(await self.demo_task_host.create_link())
    await self.switch.add_link(await self.task_manager_web.create_link())
    await self.switch.add_link(await self.task_manager.create_link())

    self.client = await self.create_client()
    self.client.start()
    self.tm_client = TaskManagerClient(self.client)


    self.tasks.append(asyncio.create_task(self.discovery_worker.run()))
    await wait_for_topic_signal(self.client, NetworkTopics.DISCOVERY_SIGNAL)

    self.tasks.append(asyncio.create_task(self.task_manager.run()))
    self.tasks.append(asyncio.create_task(self.task_manager_web.run()))
    self.demo_task_host_task = asyncio.create_task(self.demo_task_host.run())
    self.tasks.append(self.demo_task_host_task)
    await self.client.request_address()
    self.web_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=ASGIProxyApp(self.client, NetworkAddressNames.TASK_MANAGER_WEB)), base_url="http://testserver")
    await self.demo_task_host.ready.wait()

  async def asyncTearDown(self):
    try:
      del self.task_manager_web.store
      await self.web_client.aclose()
      for task in self.tasks: task.cancel()
      for task in self.tasks:
        try: await task
        except (asyncio.CancelledError, ConnectionClosedError): pass
        except: raise
      self.switch.stop_receiving()
    finally:
      TestTaskSystem.lock.release()

  async def create_client(self):
    client = Client(await self.switch.add_local_connection())
    client.start()
    return client

  @async_timeout(1)
  async def test_registration(self):
    await self.demo_task_host.register()
    task_hosts = await self.tm_client.list_task_hosts()
    self.assertEqual(len(task_hosts), 1)
    for k, v in self.demo_task_host.metadata.items(): self.assertEqual(task_hosts[0].metadata[k], v)
    await self.demo_task_host.unregister()
    await asyncio.sleep(0.001) # HACK: we dont want sleeps
    task_hosts = await self.tm_client.list_task_hosts()
    self.assertEqual(len(task_hosts), 0)

  @async_timeout(1)
  async def test_start_cancel(self):
    await self.demo_task_host.register()
    task = await self.tm_client.schedule_start_task(self.demo_task_host.id, None)
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
    await self.demo_task_host.register()
    task = await self.tm_client.schedule_start_task(self.demo_task_host.id, None, ts_id)

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
    await self.demo_task_host.register()
    task = await self.tm_client.schedule_start_task(self.demo_task_host.id, None)
    self.assertIs(task.status, TaskStatus.running)
    self.assertIsNone(task.error)
    self.assertEqual(len(self.demo_task_host.tasks), 1)
    self.assertIn(task.id, self.demo_task_host.tasks)

    async with self.tm_client.task_receiver([ task.id ]) as receiver:
      self.demo_task_host.stop_event.set()
      updated_task = await receiver.get()
      self.assertIs(updated_task.status, TaskStatus.ended)
      self.assertIsNone(updated_task.error)
      self.assertEqual(updated_task.id, task.id)

  @async_timeout(1)
  async def test_register_unregister(self):
    await self.demo_task_host.register()
    await self.tm_client.get_task_host(self.demo_task_host.id)
    self.assertFalse(self.demo_task_host_task.done())
    with self.assertRaises(asyncio.CancelledError):
      self.demo_task_host_task.cancel()
      await self.demo_task_host_task
    with self.assertRaises(FetchError):
      await self.tm_client.get_task_host(self.demo_task_host.id)

  async def test_web_api(self):
    await self.demo_task_host.register()
    task = await self.tm_client.schedule_start_task(self.demo_task_host.id, None)

    registered_task_hosts = TaskHostRegistrationList.validate_json((await self.web_client.get("/api/task-hosts")).text)
    self.assertEqual(len(registered_task_hosts), 1)
    self.assertEqual(registered_task_hosts[0].id, self.demo_task_host.id)

    self.assertEqual((await self.web_client.get(f"/task-host/{self.demo_task_host.id}/task-host-name.txt")).text, "DemoTaskHost")
    self.assertEqual((await self.web_client.get(f"/task/{task.id}/task-name.txt")).text, "DemoTask")

    stopped_task = await self.tm_client.cancel_task_wait(task.id)
    self.assertEqual(stopped_task.id, task.id)
    self.assertEqual(stopped_task.status, TaskStatus.stopped)

if __name__ == '__main__':
  unittest.main()
