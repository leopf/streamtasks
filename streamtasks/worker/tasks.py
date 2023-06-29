from streamtasks.worker import Worker
from streamtasks.client import Client
from streamtasks.protocols import *
from streamtasks.asgi import *
import fnmatch
import re
import asyncio
from abc import ABC, abstractmethod
from typing import Iterable
from pydantic import BaseModel
import urllib.parse
from fastapi import FastAPI
import uvicorn
from uuid import uuid4
import logging

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
      found_app = next((app for (path_pattern, app) in self.list_apps() if path_pattern.match(req_path)), None)
      if found_app:
        return await found_app(scope, receive, send)
    await asgi_app_not_found(scope, receive, send)

class DashboardInfo(BaseModel):
  label: str
  key: str
  init_descriptor: str
  address: int

class TaskFactoryRegistration(BaseModel):
  id: str
  worker_address: int

  @property
  def web_init_descriptor(self) -> str: return f"task_factory_{self.id}_web"

  @property
  def deploy_descriptor(self) -> str: return f"task_factory_{self.id}_deploy"
  @property
  def delete_descriptor(self) -> str: return f"task_factory_{self.id}_delete"

class TaskDeployment(BaseModel):
  id: str
  task_factory_id: str
  title: str
  config: Any

class TaskDeploymentDelete(BaseModel):
  id: str

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

  async def async_start(self, stop_signal: asyncio.Event):
    client = Client(await self.create_connection())
    await asyncio.gather(
      self._setup(client),
      self._run_task_deployments(stop_signal, client),
      self._run_task_deletions(stop_signal, client),
      self._run_dashboard(stop_signal, client),
      super().async_start(stop_signal)
    )

  async def _setup(self, client: Client):
    await self.running.wait()
    await client.request_address()
    await client.wait_for_address_name(AddressNames.TASK_MANAGER)
    self.reg = TaskFactoryRegistration(id=self.id, worker_address=client.default_address)
    self.ready.set()

  async def _run_task_deployments(self, stop_signal: asyncio.Event, client: Client):
    await self.ready.wait()
    with client.get_fetch_request_receiver(self.reg.deploy_descriptor) as receiver:
      while not stop_signal.is_set():
        try:
          if not receiver.empty():
            req: FetchRequest = await receiver.recv()
            deployment: TaskDeployment = TaskDeployment.parse_obj(req.body)
            await self.deploy(deployment)
            await req.respond(None)
          else: await asyncio.sleep(0.001)
        except Exception as e: logging.error(e)

  async def _run_task_deletions(self, stop_signal: asyncio.Event, client: Client):
    await self.ready.wait()
    with client.get_fetch_request_receiver(self.reg.delete_descriptor) as receiver:
      while not stop_signal.is_set():
        try:
          if not receiver.empty():
            req: FetchRequest = await receiver.recv()
            deployment: TaskDeploymentDelete = TaskDeploymentDelete.parse_obj(req.body)
            await self.delete(deployment)
            await req.respond(None)
          else: await asyncio.sleep(0.001)
        except Exception as e: logging.error(e)

  async def _run_dashboard(self, stop_signal: asyncio.Event, client: Client):
    await self.ready.wait()

    await client.fetch(AddressNames.TASK_MANAGER, "register_task_factory", self.reg.dict())

    app = FastAPI()

    runner = ASGIAppRunner(client, app, self.reg.web_init_descriptor, self.reg.worker_address)
    await runner.async_start(stop_signal)

  async def delete(self, deployment: TaskDeploymentDelete):
    if deployment.id not in self.tasks: return
    task: Task = self.tasks[deployment.id]
    await task.stop(self.stop_timeout)
    del self.tasks[deployment.id]

  async def deploy(self, deployment: TaskDeployment):
    if deployment.id in self.tasks:
      task: Task = self.tasks[deployment.id]
      if task.can_update(deployment): 
        await task.update(deployment)
        return
      else: await task.stop(self.stop_timeout)

    task = await self.create_task(deployment)
    self.tasks[deployment.id] = task

  @abstractmethod
  async def create_task(self, deployment: TaskDeployment) -> Task: pass

class ASGIDashboardRouter(ASGIRouterBase):
  def __init__(self, client: Client, base_url: str):
    super().__init__(base_url)
    self.client = client
    self._dashboards = {}

  def remove_dashboard(self, key: str): self._dashboards.pop(key, None)
  def add_dashboard(self, dashboard: DashboardInfo):
    proxy_app = ASGIProxyApp(self.client, dashboard.address, dashboard.init_descriptor, self.client.default_address)
    db_base_url = f"/{urllib.parse.quote(dashboard.key)}"
    path_pattern = fnmatch.translate(f"{db_base_url}/**") # TODO: is this good enough?
    self._dashboards[dashboard.key] = (path_pattern, proxy_app, db_base_url, dashboard.label)

  def list_dashboards(self):
    return [ { "key": key, "path": urllib.parse.urljoin(self.base_url, data[2]), "label": data[3] } for key, data in self._dashboards.items()]
  def list_apps(self) -> Iterable[tuple[re.Pattern, ASGIApp]]:
    return [(path_pattern, app) for (path_pattern, app, _, _) in self._dashboards.values()]

class TaskManagerWorker(Worker):
  def __init__(self, node_id: int, port: int, host: str = "127.0.0.1"):
    super().__init__(node_id)
    self.ready = asyncio.Event()
    self.port = port
    self.host = host

  async def async_start(self, stop_signal: asyncio.Event):
    client = Client(await self.create_connection())
    self.dashboard_router = ASGIDashboardRouter(client, "/dashboard/")

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

  async def _run_dashboard(self, stop_signal: asyncio.Event, client: Client):
    app = FastAPI()

    @app.get("/dashboards")
    def list_dashboards(): return self.dashboard_router.list_dashboards()

    app.mount(self.dashboard_router.base_url, self.dashboard_router)

    config = uvicorn.Config(app, port=self.port, host=self.host)
    server = uvicorn.Server(config)
    await server.serve()