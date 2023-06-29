from streamtasks.worker import Worker
from streamtasks.client import Client
from streamtasks.protocols import *
from streamtasks.asgi import *
import fnmatch
import re
import asyncio
from abc import ABC, abstractmethod, abstractproperty
from typing import Iterable
from pydantic import BaseModel
import urllib.parse
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import uvicorn
from uuid import uuid4
import logging

class DashboardInfo(BaseModel):
  label: str
  id: str
  address: int

  @property
  def web_init_descriptor(self) -> str: return f"task_factory_{self.id}_web"

class DashboardDeleteMessage(BaseModel):
  id: str

class TaskFactoryRegistration(BaseModel):
  id: str
  worker_address: int

  @property
  def web_init_descriptor(self) -> str: return f"task_factory_{self.id}_web"

class TaskFactoryDeleteMessage(BaseModel):
  id: str

class TaskStreamFormat(BaseModel):
  label: str
  multiple: Optional[bool]
  content_type: Optional[str]
  encoding: Optional[str]

class TaskStream(TaskStreamFormat):
  topic_id: str

class TaskStreamFormatGroup(BaseModel):
  label: Optional[str]
  inputs: list[TaskStreamFormat]
  outputs: list[TaskStreamFormat]

class TaskStreamGroup(BaseModel):
  label: Optional[str]
  inputs: list[TaskStream]
  outputs: list[TaskStream]

class TaskFormat(BaseModel):
  task_factory_id: str
  label: str
  hostname: str
  worker_id: str
  stream_groups: list[TaskStreamFormatGroup]

class TaskDeployment(BaseModel):
  id: str
  task_factory_id: str
  label: str
  config: Any
  stream_groups: list[TaskStreamGroup]
  topic_id_map: dict[str, int]

class TaskDeploymentDeleteMessage(BaseModel):
  id: str

class TaskFetchDescriptors:
  REGISTER_TASK_FACTORY = "register_task_factory"
  UNREGISTER_TASK_FACTORY = "unregister_task_factory"
  DEPLOY_TASK = "deploy_task"
  DELETE_TASK = "delete_task"
  REGISTER_DASHBOARD = "register_dashboard"
  UNREGISTER_DASHBOARD = "unregister_dashboard"

def asgi_app_not_found(scope, receive, send):
  await send({"type": "http.response.start", "status": 404})
  await send({"type": "http.response.body", "body": b"404 Not Found"})

class ASGIRouterBase(ABC):
  def __init__(self, base_url: str):
    self.base_url = base_url

  @abstractmethod
  def list_apps(self) -> Iterable[tuple[re.Pattern, ASGIApp]]: pass

  async def __call__(self, scope, receive, send):
    if "path" in scope: 
      req_path = scope["path"].decode("utf-8")
      found_app = next((app for (path_pattern, app) in self.list_apps() if path_pattern.match(req_path)), None)
      if found_app:
        return await found_app(scope, receive, send)
    await asgi_app_not_found(scope, receive, send)


class ASGIDashboardRouter(ASGIRouterBase):
  def __init__(self, client: Client, base_url: str):
    super().__init__(base_url)
    self.client = client
    self._dashboards = {}

  def remove_dashboard(self, id: str): self._dashboards.pop(id, None)
  def add_dashboard(self, dashboard: DashboardInfo):
    proxy_app = ASGIProxyApp(self.client, dashboard.address, dashboard.web_init_descriptor, self.client.default_address)
    db_base_url = f"/{urllib.parse.quote(dashboard.id)}"
    path_pattern = fnmatch.translate(f"{db_base_url}/**") # TODO: is this good enough?
    self._dashboards[dashboard.id] = (path_pattern, proxy_app, db_base_url, dashboard.label)

  def list_dashboards(self):
    return [ { "key": key, "path": urllib.parse.urljoin(self.base_url, data[2]), "label": data[3] } for key, data in self._dashboards.items()]
  def list_apps(self) -> Iterable[tuple[re.Pattern, ASGIApp]]:
    return [(path_pattern, app) for (path_pattern, app, _, _) in self._dashboards.values()]

class ASGITaskFactoryRouter(ASGIRouterBase):
  def __init__(self, client: Client, base_url: str):
    super().__init__(base_url)
    self.client = client
    self._task_factories = {}

  def remove_task_factory(self, id: str): self._task_factories.pop(id, None)
  def add_task_factory(self, task_factory: TaskFactoryRegistration):
    proxy_app = ASGIProxyApp(self.client, task_factory.worker_address, task_factory.web_init_descriptor, self.client.default_address)
    tf_base_url = f"/{urllib.parse.quote(task_factory.id)}"
    path_pattern = fnmatch.translate(f"{tf_base_url}/**")
    self._task_factories[task_factory.id] = (path_pattern, proxy_app, tf_base_url)

  def list_task_factories(self): return [ { "id": id, "path": urllib.parse.urljoin(self.base_url, data[2]) } for id, data in self._task_factories.items()]
  def list_apps(self) -> Iterable[tuple[re.Pattern, ASGIApp]]: return [(path_pattern, app) for (path_pattern, app, _) in self._task_factories.values()]

class Task(ABC):
  def __init__(self):
    self._task = None
    self._stop_signal = asyncio.Event()
    self.app = asgi_app_not_found

  def can_update(self, deployment: TaskDeployment): return False
  async def update(self, deployment: TaskDeployment): pass
  async def stop(self, timeout: float = None): 
    if self._task is None: raise RuntimeError("Task not started")
    self._stop_signal.set()
    try: await asyncio.wait_for(self._task, timeout=timeout)
    except asyncio.TimeoutError: pass
  async def start(self):
    if self._task is not None: raise RuntimeError("Task already started")
    self._task = asyncio.create_task(self._run(self._stop_signal))

  @abstractmethod
  async def async_start(self, stop_signal: asyncio.Event): pass

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
      await req.respond(None)

    @server.route(TaskFetchDescriptors.DEPLOY_TASK)
    async def deploy_task(req: FetchRequest):
      deployment: TaskDeployment = TaskDeployment.parse_obj(req.body)
      await self.deploy_task(deployment)
      await req.respond(None)

    await server.async_start(self._stop_signal)

  async def _run_dashboard(self):
    await self.ready.wait()

    await self._client.fetch(AddressNames.TASK_MANAGER, TaskFetchDescriptors.REGISTER_TASK_FACTORY, self.reg.dict())

    app = FastAPI()

    @app.get("/config.js")
    async def config_js(): return PlainTextResponse(await self.read_config_script(), media_type="application/javascript")

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

  @abstractproperty
  def task_format(self) -> TaskFormat: return None
  @abstractmethod
  async def read_config_script(self) -> str: pass
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
  def __init__(self, node_id: int, port: int, host: str = "127.0.0.1"):
    super().__init__(node_id)
    self.ready = asyncio.Event()
    self.port = port
    self.host = host

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
      await req.respond(None)  

    @server.route(TaskFetchDescriptors.UNREGISTER_TASK_FACTORY)
    async def unregister_task_factory(req: FetchRequest):
      registration: TaskFactoryDeleteMessage = TaskFactoryDeleteMessage.parse_obj(req.body)
      self.task_factory_router.remove_task_factory(registration.id)
      await req.respond(None)

    @server.route(TaskFetchDescriptors.REGISTER_DASHBOARD)
    async def register_dashboard(req: FetchRequest):
      dashboard: DashboardInfo = DashboardInfo.parse_obj(req.body)
      self.dashboard_router.add_dashboard(dashboard)
      await req.respond(None)

    @server.route(TaskFetchDescriptors.UNREGISTER_DASHBOARD)
    async def unregister_dashboard(req: FetchRequest):
      dashboard: DashboardDeleteMessage = DashboardDeleteMessage.parse_obj(req.body)
      self.dashboard_router.remove_dashboard(dashboard.id)
      await req.respond(None)

  async def _run_dashboard(self, stop_signal: asyncio.Event, client: Client):
    app = FastAPI()

    @app.get("/dashboards")
    def list_dashboards(): return self.dashboard_router.list_dashboards()

    app.mount(self.dashboard_router.base_url, self.dashboard_router)

    config = uvicorn.Config(app, port=self.port, host=self.host)
    server = uvicorn.Server(config)
    await server.serve()