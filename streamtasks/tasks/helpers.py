from abc import ABC, abstractmethod
from typing import Iterable
from streamtasks.asgi import ASGIApp
from streamtasks.client import Client
from streamtasks.protocols import *
from streamtasks.tasks.types import TaskFactoryRegistration, DashboardInfo, TaskFactoryInfo
from streamtasks.asgi import *
import fnmatch
import urllib.parse
import uvicorn
import re
import asyncio
import httpx

async def asgi_app_not_found(scope, receive, send):
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

class ASGIServer(ABC):
  @abstractmethod
  async def serve(self, app: ASGIApp): pass

class ASGITestServer(ASGIServer):
  def __init__(self, hostname: str = "testserver"):
    self._app = None
    self._hostname = hostname
    self._waiter = asyncio.Event()
  async def serve(self, app: ASGIApp):
    self._app = app
    self._waiter.set()
  async def wait_for_client(self):
    await self._waiter.wait()
    transport = httpx.ASGITransport(app=self._app)
    client = httpx.AsyncClient(transport=transport, base_url="http://" + self._hostname)
    return client
class UvicornASGIServer(ASGIServer):
  def __init__(self, port: int, host: str = "127.0.0.1"):
    super().__init__()
    self.port = port
    self.host = host
  async def serve(self, app: ASGIApp):
    config = uvicorn.Config(app, port=self.port, host=self.host)
    server = uvicorn.Server(config)
    await server.serve()

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
    self._task_factory_apps = {}
    self._task_factories = {}
    self._task_facotry_infos = {}

  def remove_task_factory(self, id: str): 
    self._task_factories.pop(id, None)
    self._task_facotry_infos.pop(id, None)
    self._task_factory_apps.pop(id, None)

  def add_task_factory(self, task_factory: TaskFactoryRegistration):
    proxy_app = ASGIProxyApp(self.client, task_factory.worker_address, task_factory.web_init_descriptor, self.client.default_address)
    tf_base_url = f"/{urllib.parse.quote(task_factory.id)}"
    path_pattern = fnmatch.translate(f"{tf_base_url}/**")
    self._task_factory_apps[task_factory.id] = (path_pattern, proxy_app)
    self._task_factories[task_factory.id] = task_factory
    self._task_facotry_infos[task_factory.id] = TaskFactoryInfo(id=task_factory.id, path=urllib.parse.urljoin(self.base_url, tf_base_url))

  def get_task_factory(self, id: str) -> Optional[TaskFactoryRegistration]: 
    return self._task_factories.get(id, None)

  def list_task_factory_infos(self): return self._task_facotry_infos.values()
  def list_apps(self) -> Iterable[tuple[re.Pattern, ASGIApp]]: return self._task_factories.values()

