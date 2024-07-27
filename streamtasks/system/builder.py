import asyncio
import functools
import logging
from streamtasks.asgi import HTTPServerOverASGI
from streamtasks.client import Client
from streamtasks.client.discovery import wait_for_topic_signal
from streamtasks.connection import AutoReconnector, NodeServer, connect, get_server
from streamtasks.error import PlatformNotSupportedError
from streamtasks.net import Switch
from streamtasks.services.discovery import DiscoveryWorker
from streamtasks.services.protocols import AddressNames, WorkerTopics
from streamtasks.system.connection_manager import ConnectionManager
from streamtasks.system.helpers import get_all_task_hosts
from streamtasks.system.named_topic_manager import NamedTopicManager
from streamtasks.system.task import TaskManager
from streamtasks.system.task_web import TaskWebBackend

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
    await self.start_task_system()

  async def start_discovery(self): self._add_task(DiscoveryWorker(await self.switch.add_local_connection()).run())

  async def start_connector(self, url: str | None = None):
    self._add_task(AutoReconnector(await self.switch.add_local_connection(), functools.partial(connect, url=url)).run())

  async def start_server(self, url: str | None = None):  self._add_task(get_server(await self.switch.add_local_connection(), url).run())

  async def start_task_system(self):
    await self._wait_discovery()
    self._add_task(TaskManager(await self.switch.add_local_connection()).run())
    self._add_task(TaskWebBackend(await self.switch.add_local_connection()).run())

  async def start_named_topic_manager(self):
    await self._wait_discovery()
    self._add_task(NamedTopicManager(await self.switch.add_local_connection()).run())

  async def start_connection_manager(self):
    await self._wait_discovery()
    self._add_task(ConnectionManager(await self.switch.add_local_connection()).run())

  async def start_node_server(self):
    await self._wait_discovery()
    try:
      self._add_task(NodeServer(await self.switch.add_local_connection()).run())
    except PlatformNotSupportedError as e:
      logging.warning("Failed to start node server. Platform not supported: ", e)

  async def start_user_endpoint(self, port: int):
    await self._wait_discovery()
    worker = HTTPServerOverASGI(await self.switch.add_local_connection(), ("localhost", port), AddressNames.TASK_MANAGER_WEB)
    self.http_servers.append(worker)
    self._add_task(worker.run())

  async def start_task_hosts(self):
    for TaskHostCls in get_all_task_hosts():
      self._add_task(TaskHostCls(await self.switch.add_local_connection(), register_endpoits=[AddressNames.TASK_MANAGER]).run())

  async def wait_done(self):
    await asyncio.wait(self.tasks, return_when="FIRST_COMPLETED")
    for task in self.tasks:
      if not task.done(): task.cancel("Other task completed!")
      try: await task
      except asyncio.CancelledError: pass

  def _add_task(self, ft: asyncio.Future): self.tasks.append(asyncio.create_task(ft))
  async def _wait_discovery(self):
    if not self.disovery_ready:
      client = Client(await self.switch.add_local_connection())
      client.start()
      await asyncio.wait_for(wait_for_topic_signal(client, WorkerTopics.DISCOVERY_SIGNAL), 2)
      self.disovery_ready = True
