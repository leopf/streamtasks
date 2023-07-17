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

  async def start_task(self, task: DeploymentTask):
    factory = self._task_factories.get(task.task_factory_id, None)
    if factory is None: raise RuntimeError(f"Task factory with id {task_factory_id} not found")
    response = await self.client.fetch(factory.worker_address, TaskFetchDescriptors.DEPLOY_TASK, task.model_dump())
    return TaskDeploymentStatus.model_validate(response)

  async def delete_task(self, task_factory_id: str, task_id: str):
    factory = self._task_factories.get(task_factory_id, None)
    if factory is None: raise RuntimeError(f"Task factory with id {task_factory_id} not found")
    response = await self.client.fetch(factory.worker_address, TaskFetchDescriptors.DELETE_TASK, TaskDeploymentDeleteMessage(id=task_id).model_dump())
    return TaskDeploymentStatus.model_validate(response)

  def add_task_factory(self, task_factory: TaskFactoryRegistration): 
    proxy_app = ASGIProxyApp(self.client, task_factory.worker_address, task_factory.web_init_descriptor, self.client.default_address)
    self.router.add_app(task_factory.id, proxy_app)
    self._task_factories[task_factory.id] = task_factory

  def remove_task_factory(self, id: str): 
    self.router.remove_app(id)
    self._task_factories.pop(id, None)

class DeploymentStore:
  def __init__(self):
    self._deployments = {}
    self._started_deployments = {}
  
  @property
  def deployments(self): return [ DeploymentBase(**deployment.model_dump()) for deployment in self._deployments.values() ]

  def has_deployment(self, id: str) -> bool: return id in self._deployments
  def set_deployment_started(self, deployment: Deployment):
    new_deployment = deployment.copy(deep=True)
    self._started_deployments[deployment.id] = new_deployment
    return new_deployment

  def set_deployment_stopped(self, deployment: Deployment):
    self._started_deployments.pop(deployment.id, None)
  
  def get_deployment_status(self, id: str) -> DeploymentStatusInfo:
    started_deployment = self.get_started_deployment(id)
    if started_deployment is not None: return DeploymentStatusInfo(status=started_deployment.status, started=True)
    deployment = self.get_deployment(id)
    if deployment is None: raise RuntimeError(f"Deployment with id {id} not found")
    return DeploymentStatusInfo(status=deployment.status, started=False)

  def get_started_deployment(self, id: str) -> Optional[Deployment]:
    return self._started_deployments.get(id, None)

  def get_deployment(self, id: str) -> Optional[Deployment]:
    return self._deployments.get(id, None)

  def deployment_was_started(self, id: str) -> bool:
    return id in self._started_deployments

  def store_deployment(self, deployment: Deployment):
    self._deployments[deployment.id] = deployment

  def remove_deployment(self, id: str):
    self._deployments.pop(id, None)
