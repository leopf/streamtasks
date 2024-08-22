import asyncio
import functools
from streamtasks.asgi import HTTPServerOverASGI
from streamtasks.client import Client
from streamtasks.client.discovery import wait_for_topic_signal
from streamtasks.connection import AutoReconnector, connect, create_server
from streamtasks.net import Switch
from streamtasks.services.discovery import DiscoveryWorker
from streamtasks.services.protocols import AddressNames, NetworkTopics
from streamtasks.system.connection_manager import ConnectionManager
from streamtasks.system.helpers import get_all_task_hosts
from streamtasks.system.named_topic_manager import NamedTopicManager
from streamtasks.system.secret_manager import SecretManager
from streamtasks.system.task import TaskManager
from streamtasks.system.task_web import TaskWebBackend
from streamtasks.worker import Worker

class SystemBuilder:
  def __init__(self):
    self.switch = Switch()
    self.tasks: list[asyncio.Future] = []
    self.http_servers: list[HTTPServerOverASGI] = []
    self.disovery_ready = False

  async def start_system(self, ui_port: int):
    await self.start_connection_manager()
    await self.start_user_endpoint(ui_port)
    await self.start_node_server()
    await self.start_task_hosts()

  async def start_core(self):
    await self.start_discovery()
    await self.start_named_topic_manager()
    await self.start_secret_manager()
    await self.start_task_system()

  async def start_discovery(self): await self._start_worker(DiscoveryWorker())
  async def start_connector(self, url: str | None = None):
    await self._start_worker(AutoReconnector(functools.partial(connect, url=url)))

  async def start_server(self, url: str | None = None): await self._start_worker(create_server(url))
  async def start_node_server(self): await self.start_server()

  async def start_task_system(self):
    await self._wait_discovery()
    await self._start_worker(TaskManager())
    await self._start_worker(TaskWebBackend())

  async def start_named_topic_manager(self):
    await self._wait_discovery()
    await self._start_worker(NamedTopicManager())

  async def start_secret_manager(self):
    await self._wait_discovery()
    await self._start_worker(SecretManager())

  async def start_connection_manager(self):
    await self._wait_discovery()
    await self._start_worker(ConnectionManager())

  async def start_user_endpoint(self, port: int):
    await self._wait_discovery()
    worker = HTTPServerOverASGI(("localhost", port), AddressNames.TASK_MANAGER_WEB)
    self.http_servers.append(worker)
    await self._start_worker(worker)

  async def start_task_hosts(self):
    for TaskHostCls in get_all_task_hosts():
      await self._start_worker(TaskHostCls(register_endpoits=[AddressNames.TASK_MANAGER]))

  async def wait_done(self):
    await asyncio.wait(self.tasks, return_when="FIRST_COMPLETED")
    for task in self.tasks:
      if not task.done(): task.cancel("Other task completed!")
      try: await task
      except asyncio.CancelledError: pass

  def cancel_all(self):
    for task in self.tasks: task.cancel()

  async def _start_worker(self, worker: Worker):
    await self.switch.add_link(await worker.create_link())
    self._add_task(worker.run())

  def _add_task(self, ft: asyncio.Future): self.tasks.append(asyncio.create_task(ft))
  async def _wait_discovery(self):
    if not self.disovery_ready:
      client = Client(await self.switch.add_local_connection())
      client.start()
      await asyncio.wait_for(wait_for_topic_signal(client, NetworkTopics.DISCOVERY_SIGNAL), 2)
      self.disovery_ready = True
