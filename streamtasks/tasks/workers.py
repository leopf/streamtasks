import asyncio
from abc import ABC, abstractmethod, abstractproperty
from typing import Iterable
from streamtasks.asgi import ASGIApp
import uvicorn
import re
from streamtasks.protocols import *
from streamtasks.client import Client
from streamtasks.asgi import *
from streamtasks.worker import Worker
from streamtasks.tasks.task import Task
from streamtasks.tasks.types import TaskDeployment, TaskDeploymentDeleteMessage, TaskFactoryRegistration, TaskFactoryDeleteMessage, DashboardInfo, DashboardDeleteMessage
from uuid import uuid4
import urllib.parse
from fastapi.responses import PlainTextResponse
from fastapi import FastAPI


class TaskFactoryWorker(Worker, ABC):
  def __init__(self):
    self.id = str(uuid4())
    self.tasks = {}
    self.ready = asyncio.Event()
    self.stop_timeout = 2
    self._stop_signal = None
    self._client = None

  async def async_start(self, stop_signal: asyncio.Event):
    self._stop_signal = stop_signal
    self._client = Client(await self.create_connection())
    await asyncio.gather(
      self._setup(),
      self._run_fetch_server(),
      self._run_dashboard(),
      super().async_start(stop_signal)
    )

  async def _setup(self):
    await self.running.wait()
    await self._client.request_address()
    await self._client.wait_for_address_name(AddressNames.TASK_MANAGER)
    self.reg = TaskFactoryRegistration(id=self.id, worker_address=self._client.default_address)
    self.ready.set()

  async def _run_fetch_server(self):
    await self.ready.wait()

    server = self._client.create_fetch_server()

    @server.route(TaskFetchDescriptors.DELETE_TASK)
    async def delete_task(req: FetchRequest):
      deployment: TaskDeploymentDeleteMessage = TaskDeploymentDeleteMessage.parse_obj(req.body)
      await self.delete_task(deployment)

    @server.route(TaskFetchDescriptors.DEPLOY_TASK)
    async def deploy_task(req: FetchRequest):
      deployment: TaskDeployment = TaskDeployment.parse_obj(req.body)
      await self.deploy_task(deployment)

    await server.async_start(self._stop_signal)

  async def _run_dashboard(self):
    await self.ready.wait()

    await self._client.fetch(AddressNames.TASK_MANAGER, TaskFetchDescriptors.REGISTER_TASK_FACTORY, self.reg.dict())

    app = FastAPI()

    @app.get("/config.js")
    async def config_js(): return PlainTextResponse(self.config_script, media_type="application/javascript")

    @app.get("/task-format.json")
    async def task_format(): return self.task_format.dict()

    runner = ASGIAppRunner(self._client, app, self.reg.web_init_descriptor, self.reg.worker_address)
    await runner.async_start(self._stop_signal)

  async def delete_task(self, deployment: TaskDeploymentDeleteMessage):
    if deployment.id not in self.tasks: return
    task: Task = self.tasks[deployment.id]
    await task.stop(self.stop_timeout)
    del self.tasks[deployment.id]
  async def deploy_task(self, deployment: TaskDeployment):
    if deployment.id in self.tasks:
      task: Task = self.tasks[deployment.id]
      if task.can_update(deployment): 
        await task.update(deployment)
        return
      else: await task.stop(self.stop_timeout)
    task = await self.create_task(deployment)
    self.tasks[deployment.id] = task
  async def create_client(self) -> Client: return Client(await self.create_connection())
  @abstractproperty
  def task_format(self) -> TaskFormat: return None
  @abstractproperty
  def config_script(self) -> str: pass
  @abstractmethod
  async def create_task(self, deployment: TaskDeployment) -> Task: pass

# TODO: this needs the actual dashboard
class NodeManagerWorker(Worker):
  def __init__(self, node_id: int):
    super().__init__(node_id)
    self.async_tasks = []
    self._stop_signal = None
    self._client = None

  async def async_start(self, stop_signal: asyncio.Event):
    self._stop_signal = stop_signal
    self._client = Client(await self.create_connection())
    await asyncio.gather(
      super().async_start(stop_signal)
    )
    for task in self.async_tasks: await task
  async def unregister_dashboard(self, key: str):
    self._client.fetch(AddressNames.TASK_MANAGER, TaskFetchDescriptors.UNREGISTER_DASHBOARD, DashboardDeleteMessage(key=key).dict())
  async def register_dashboard(self, label: str, app: ASGIApp):
    id = str(uuid4())
    dashboard = DashboardInfo(label=label, id=id, init_descriptor=f"global_dashboard_${id}", address=self._client.default_address)
    runner = ASGIAppRunner(self._client, app, dashboard.web_init_descriptor, dashboard.address)
    self.async_tasks.append(asyncio.create_task(runner.async_start(self._stop_signal)))
    await self._client.fetch(AddressNames.TASK_MANAGER, TaskFetchDescriptors.REGISTER_DASHBOARD, dashboard.dict())
    return id

class TaskManagerWorker(Worker):
  def __init__(self, node_id: int, asgi_server: ASGIServer):
    super().__init__(node_id)
    self.ready = asyncio.Event()
    self.asgi_server = asgi_server

  async def async_start(self, stop_signal: asyncio.Event):
    client = Client(await self.create_connection())
    self.dashboard_router = ASGIDashboardRouter(client, "/dashboard/")
    self.task_factory_router = ASGITaskFactoryRouter(client, "/task-factory/")

    await asyncio.gather(
      self._setup(client),
      self._run_dashboard(stop_signal, client),
      super().async_start(stop_signal)
    )

  async def _setup(self, client: Client):
    await self.running.wait()
    await client.wait_for_topic_signal(WorkerTopics.DISCOVERY_SIGNAL)
    await client.request_address()
    await client.register_address_name(AddressNames.TASK_MANAGER)
    self.ready.set()

  async def _run_fetch_server(self, stop_signal: asyncio.Event, client: Client):
    await self.ready.wait()
    server = client.create_fetch_server()

    @server.route(TaskFetchDescriptors.REGISTER_TASK_FACTORY)
    async def register_task_factory(req: FetchRequest):
      registration: TaskFactoryRegistration = TaskFactoryRegistration.parse_obj(req.body)
      self.task_factory_router.add_task_factory(registration)

    @server.route(TaskFetchDescriptors.UNREGISTER_TASK_FACTORY)
    async def unregister_task_factory(req: FetchRequest):
      registration: TaskFactoryDeleteMessage = TaskFactoryDeleteMessage.parse_obj(req.body)
      self.task_factory_router.remove_task_factory(registration.id)

    @server.route(TaskFetchDescriptors.REGISTER_DASHBOARD)
    async def register_dashboard(req: FetchRequest):
      dashboard: DashboardInfo = DashboardInfo.parse_obj(req.body)
      self.dashboard_router.add_dashboard(dashboard)

    @server.route(TaskFetchDescriptors.UNREGISTER_DASHBOARD)
    async def unregister_dashboard(req: FetchRequest):
      dashboard: DashboardDeleteMessage = DashboardDeleteMessage.parse_obj(req.body)
      self.dashboard_router.remove_dashboard(dashboard.id)

    await server.async_start(stop_signal)

  async def _run_dashboard(self, stop_signal: asyncio.Event, client: Client):
    app = FastAPI()

    @app.get("/dashboards")
    def list_dashboards(): return self.dashboard_router.list_dashboards()

    app.mount(self.dashboard_router.base_url, self.dashboard_router)

    await self.asgi_server.serve(app)