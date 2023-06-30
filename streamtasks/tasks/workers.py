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
from streamtasks.tasks.types import *
from streamtasks.tasks.helpers import *
from uuid import uuid4
import urllib.parse
from fastapi.responses import PlainTextResponse
from fastapi import FastAPI
import itertools


class TaskFactoryWorker(Worker, ABC):
  def __init__(self, node_id: int):
    super().__init__(node_id)
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
    await self._client.fetch(AddressNames.TASK_MANAGER, TaskFetchDescriptors.REGISTER_TASK_FACTORY, self.reg.dict())
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
  def task_format(self) -> TaskFormat: pass
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

    self.deployments = {}

    self.dashboard_router = None
    self.task_factory_router = None

  async def async_start(self, stop_signal: asyncio.Event):
    client = Client(await self.create_connection())
    self.dashboard_router = ASGIDashboardRouter(client, "/dashboard/")
    self.task_factory_router = ASGITaskFactoryRouter(client, "/task-factory/")

    await asyncio.gather(
      self._setup(client),
      self._run_web_server(stop_signal, client),
      super().async_start(stop_signal)
    )

  async def _setup(self, client: Client):
    await self.running.wait()
    await client.wait_for_topic_signal(WorkerTopics.DISCOVERY_SIGNAL)
    await client.request_address()
    self.ready.set()
    await client.register_address_name(AddressNames.TASK_MANAGER)

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

  async def _run_web_server(self, stop_signal: asyncio.Event, client: Client):
    await self.ready.wait()
    app = FastAPI()

    @app.get("/dashboards")
    def list_dashboards(): return self.dashboard_router.list_dashboards()
    app.mount(self.dashboard_router.base_url, self.dashboard_router)

    @app.get("/api/deployment/{id}/status")
    def get_deployment_status(id: str):
      deployment = self.deployments.get(id, None)
      if deployment is None: raise HTTPException(status_code=404, detail="not found")
      return deployment.status

    @app.post("/api/deployment/{id}/stop")
    async def stop_deployment(id: str):
      deployment = self.deployments.get(id, None)
      if deployment is None: raise HTTPException(status_code=404, detail="not found")
      asyncio.create_task(self.stop_deployment(client, deployment))
      return deployment.dict()

    @app.post("/api/deployment/{id}/start")
    async def start_deployment(id: str):
      deployment = self.deployments.get(id, None)
      if deployment is None: raise HTTPException(status_code=404, detail="not found")
      asyncio.create_task(self.start_deployment(client, deployment))
      return deployment.dict()

    @app.delete("/api/deployment/{id}")
    async def delete_deployment(id: str):
      deployment = self.deployments.get(id, None)
      if deployment is None: raise HTTPException(status_code=404, detail="not found")
      asyncio.create_task(self.stop_deployment(client, deployment))
      del self.deployments[id]
      return deployment.dict()

    @app.get("/api/deployment/{id}")
    async def get_deployment(id: str):
      deployment = self.deployments.get(id, None)
      if deployment is None: raise HTTPException(status_code=404, detail="not found")
      return deployment.dict()

    @app.post("/api/deployment")
    async def create_deployment(tasks: list[TaskDeploymentBase]):
      topic_str_ids = set(itertools.chain.from_iterable(task.get_topic_ids() for task in tasks))
      topic_int_ids = await client.request_topic_ids(len(topic_str_ids))
      topic_id_map = { topic_str_id: topic_int_id for topic_str_id, topic_int_id in zip(topic_str_ids, topic_int_ids) }
      deployment = Deployment(id=str(uuid4()), status="offline", tasks=[ TaskDeployment(
        id=str(uuid4()),
        topic_id_map={ k: topic_id_map[k] for k in set(deployment.get_topic_ids()) },
        **deployment.dict()
      ) for deployment in tasks ])

      self.deployments[deployment.id] = deployment
      return deployment.dict()
    
    await self.asgi_server.serve(app)

  async def _stop_task_deployments(self, client: Client, tasks: list[TaskDeployment]):
    for task in tasks:
      factory: TaskFactoryRegistration = self.task_factory_router.get_task_factory(task.task_factory_id)
      if factory is None: 
        logging.error(f"task factory {task.task_factory_id} not found while deleting deployment {task.id}")
        continue
      await client.fetch(factory.worker_address, TaskFetchDescriptors.DELETE_TASK, TaskDeploymentDeleteMessage(id=task.id).dict())
  
  async def stop_deployment(self, client: Client, deployment: Deployment):
    await self._stop_task_deployments(client, deployment.tasks)
    deployment.status = "stopped"

  async def start_deployment(self, client: Client, deployment: Deployment):
    deployment.status = "starting"
    deployed_tasks = []
    try:
      for task in deployment.tasks:
        factory: TaskFactoryRegistration = self.task_factory_router.get_task_factory(task.task_factory_id)
        if factory is None: raise RuntimeError(f"task factory {task.task_factory_id} not found!")
        await client.fetch(factory.worker_address, TaskFetchDescriptors.DEPLOY_TASK, task.dict())
        deployed_tasks.append(task)
    except Exception as e:
      logging.error(f"failed to deploy tasks for deployment {deployment.id}: {e}")
      await self._stop_task_deployments(client, deployed_tasks)
      deployment.status = "failed"
      return
    deployment.status = "running"