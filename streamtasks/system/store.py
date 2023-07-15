from streamtasks.client import Client
from streamtasks.system.types import *
from streamtasks.asgi import *
from streamtasks.system.helpers import ASGIIDRouter
import urllib.parse
import asyncio

class DashboardStore:
  def __init__(self, client: Client, base_path: str):
    self.client = client
    self.base_url = base_path
    self.router = ASGIIDRouter()
    self._dashboards = []

  @property
  def dashboards(self): return [ DashboardInfo(id=db.id, path=self.router.get_path_to_id(db.id, self.base_url), label=db.label) for db in self._dashboards ]

  def add_dashboard(self, dashboard: DashboardRegistration): 
    proxy_app = ASGIProxyApp(self.client, dashboard.address, dashboard.web_init_descriptor, self.client.default_address)
    self.router.add_app(dashboard.id, proxy_app)
    self._dashboards.append(dashboard)

  def remove_dashboard(self, id: str): 
    self.router.remove_app(id)
    self._dashboards = [db for db in self._dashboards if db.id != id]

class TaskFactoryStore: 
  def __init__(self, client: Client, base_path: str):
    self.client = client
    self.base_url = base_path
    self.router = ASGIIDRouter()
    self._task_factories = {}

  @property
  def task_templates(self): return [ tf.task_template for tf in self._task_factories.values() ]

  async def start_task(self, task: DeploymentTaskFull):
    factory = self._task_factories.get(task.task_factory_id, None)
    if factory is None: raise RuntimeError(f"Task factory with id {task_factory_id} not found")
    response = await self.client.fetch(factory.worker_address, TaskFetchDescriptors.DEPLOY_TASK, task.dict())
    return TaskDeploymentStatus.parse_obj(response)

  async def delete_task(self, task_factory_id: str, task_id: str):
    factory = self._task_factories.get(task_factory_id, None)
    if factory is None: raise RuntimeError(f"Task factory with id {task_factory_id} not found")
    response = await self.client.fetch(factory.worker_address, TaskFetchDescriptors.DELETE_TASK, TaskDeploymentDeleteMessage(id=task_id).dict())
    return TaskDeploymentStatus.parse_obj(response)

  def add_task_factory(self, task_factory: TaskFactoryRegistration): 
    proxy_app = ASGIProxyApp(self.client, task_factory.worker_address, task_factory.web_init_descriptor, self.client.default_address)
    self.router.add_app(task_factory.id, proxy_app)
    self._task_factories[task_factory.id] = task_factory

  def remove_task_factory(self, id: str): 
    self.router.remove_app(id)
    self._task_factories.pop(id, None)