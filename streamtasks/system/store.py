from streamtasks.client import Client
from streamtasks.system.types import *
from streamtasks.asgi import *
from streamtasks.system.helpers import ASGIIDRouter
from tinydb.table import Table as TinyDBTable
from tinydb import Query as TinyDBQuery

class DashboardStore:
  def __init__(self, client: Client, base_path: str):
    self.client = client
    self.base_url = base_path
    self.router = ASGIIDRouter()
    self._dashboards = []

  @property
  def dashboards(self): return [ DashboardInfo(id=db.id, path=self.router.get_path_to_id(db.id, self.base_url), label=db.label) for db in self._dashboards ]

  def add_dashboard(self, dashboard: DashboardRegistration): 
    proxy_app = ASGIProxyApp(self.client, dashboard.address)
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
    if factory is None: raise RuntimeError(f"Task factory with id {task.task_factory_id} not found")
    response = await self.client.fetch(factory.worker_address, TaskFetchDescriptors.DEPLOY_TASK, task.model_dump())
    return TaskStatus.model_validate(response)

  async def delete_task(self, task_factory_id: str, task_id: str):
    factory = self._task_factories.get(task_factory_id, None)
    if factory is None: raise RuntimeError(f"Task factory with id {task_factory_id} not found")
    response = await self.client.fetch(factory.worker_address, TaskFetchDescriptors.DELETE_TASK, TaskDeploymentDeleteMessage(id=task_id).model_dump())
    return TaskStatus.model_validate(response)

  def add_task_factory(self, task_factory: TaskFactoryRegistration): 
    proxy_app = ASGIProxyApp(self.client, task_factory.worker_address)
    self.router.add_app(task_factory.id, proxy_app)
    self._task_factories[task_factory.id] = task_factory

  def remove_task_factory(self, id: str): 
    self.router.remove_app(id)
    self._task_factories.pop(id, None)

class DeploymentStore:
  def __init__(self, table: TinyDBTable):
    self._deployments_table = table
    self._started_deployments = {}
  
  @property
  def deployments(self): return [ DeploymentBase(**deployment) for deployment in self._deployments_table.all() ]

  def has_deployment(self, id: str) -> bool: return self._deployments_table.contains(TinyDBQuery().id == id)
  def set_deployment_started(self, deployment: Deployment):
    new_deployment = deployment.model_copy(deep=True)
    self._started_deployments[deployment.id] = new_deployment
    return new_deployment
  def set_deployment_stopped(self, deployment: Deployment): self._started_deployments.pop(deployment.id, None)
  def get_deployment_status(self, id: str) -> DeploymentStatusInfo:
    started_deployment = self.get_started_deployment(id)
    if started_deployment is not None: return DeploymentStatusInfo(status=started_deployment.status)
    return DeploymentStatusInfo(status="offline")
  
  def get_started_deployment(self, id: str) -> Optional[Deployment]: return self._started_deployments.get(id, None)
  def get_deployment(self, id: str) -> Optional[Deployment]:
    db_res = self._deployments_table.get(TinyDBQuery().id == id)
    if db_res is None: return None
    deployment = Deployment(**db_res)
    status_info = self.get_deployment_status(deployment.id)
    deployment.status = status_info.status
    return deployment
  
  def deployment_was_started(self, id: str) -> bool: return id in self._started_deployments
  def store_deployment(self, deployment: Deployment): self._deployments_table.upsert(deployment.model_dump(), TinyDBQuery().id == deployment.id)
  def remove_deployment(self, id: str): self._deployments_table.remove(TinyDBQuery().id == id)
