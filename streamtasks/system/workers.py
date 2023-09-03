import asyncio
from streamtasks.asgi import ASGIApp
from streamtasks.system.protocols import *
from streamtasks.client import Client
from streamtasks.comm import Connection
from streamtasks.asgi import *
from streamtasks.worker import Worker
from streamtasks.system.types import *
from streamtasks.system.helpers import *
from streamtasks.system.store import *
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request, WebSocket
import itertools
from tinydb import TinyDB
import tinydb.storages as tinydb_storages

# TODO: this needs the actual dashboard
class NodeManagerWorker(Worker):
  def __init__(self, node_connection: Connection):
    super().__init__(node_connection)
    self.async_tasks = []
    self._client = None

  async def start(self):
    try:
      self._client = Client(await self.create_connection())
      await asyncio.gather(
        super().start()
      )
    finally:
      for task in self.async_tasks: task.cancel()

  async def unregister_dashboard(self, key: str):
    self._client.fetch(AddressNames.TASK_MANAGER, TaskFetchDescriptors.UNREGISTER_DASHBOARD, DashboardDeleteMessage(key=key).model_dump())
  async def register_dashboard(self, label: str, app: ASGIApp):
    id = str(uuid4())
    dashboard = DashboardRegistration(label=label, id=id, init_descriptor=f"global_dashboard_${id}", address=self._client.default_address)
    runner = ASGIAppRunner(self._client, app, dashboard.web_init_descriptor, dashboard.address)
    self.async_tasks.append(asyncio.create_task(runner.start()))
    await self._client.fetch(AddressNames.TASK_MANAGER, TaskFetchDescriptors.REGISTER_DASHBOARD, dashboard.model_dump())
    return id

class TaskManagerWorker(Worker):
  def __init__(self, node_connection: Connection, asgi_server: ASGIServer, db_storage: type[tinydb_storages.Storage] = tinydb_storages.MemoryStorage):
    super().__init__(node_connection)
    self.ready = asyncio.Event()
    self.db = TinyDB(storage=db_storage)
    self.asgi_server = asgi_server

    self.deployments = DeploymentStore(self.db.table("deployments"))
    self.dashboards = None
    self.task_factories = None
    self.log_handler = JsonLogger()
    self.topic_id_map = {}

  async def start(self):
    try:
      logging.getLogger().addHandler(self.log_handler)
      client = Client(await self.create_connection())
      self.dashboards = DashboardStore(client, "/dashboard/")
      self.task_factories = TaskFactoryStore(client, "/task-factory/")

      await asyncio.gather(
        self._setup(client),
        self._run_web_server(client),
        self._run_fetch_server(client),
        super().start()
      )
    finally:
      self.ready.clear()
      logging.getLogger().removeHandler(self.log_handler)

  async def _setup(self, client: Client):
    await self.connected.wait()
    await client.wait_for_topic_signal(WorkerTopics.DISCOVERY_SIGNAL)
    await client.request_address()
    self.ready.set()
    await client.register_address_name(AddressNames.TASK_MANAGER)

  async def _run_fetch_server(self, client: Client):
    await self.ready.wait()
    server = client.create_fetch_server()

    @server.route(TaskFetchDescriptors.REGISTER_TASK_FACTORY)
    async def register_task_factory(req: FetchRequest):
      registration: TaskFactoryRegistration = TaskFactoryRegistration.model_validate(req.body)
      self.task_factories.add_task_factory(registration)

    @server.route(TaskFetchDescriptors.UNREGISTER_TASK_FACTORY)
    async def unregister_task_factory(req: FetchRequest):
      registration: TaskFactoryDeleteMessage = TaskFactoryDeleteMessage.model_validate(req.body)
      self.task_factories.remove_task_factory(registration.id)

    @server.route(TaskFetchDescriptors.REGISTER_DASHBOARD)
    async def register_dashboard(req: FetchRequest):
      dashboard: DashboardRegistration = DashboardRegistration.model_validate(req.body)
      self.dashboards.add_dashboard(dashboard)

    @server.route(TaskFetchDescriptors.UNREGISTER_DASHBOARD)
    async def unregister_dashboard(req: FetchRequest):
      dashboard: DashboardDeleteMessage = DashboardDeleteMessage.model_validate(req.body)
      self.dashboards.remove_dashboard(dashboard.id)

    await server.start()

  async def _run_web_server(self, client: Client):
    await self.ready.wait()
    app = FastAPI()
    app.mount(self.dashboards.base_url, self.dashboards.router)
    app.mount(self.task_factories.base_url, self.task_factories.router)

    @app.websocket("/topic/{id}/subscribe")
    async def topic_websocket(websocket: WebSocket, id: str):
      id: int = self.topic_id_map.get(id, None)
      if id is None: raise HTTPException(status_code=404, detail=f"Topic with id {id} not found!") 
      await websocket.accept()
      async with client.get_topics_receiver([ id ]) as receiver:
        while True:          
          topic_id, data, _ = await receiver.recv()
          try:
            if topic_id == id and data is not None: await websocket.send_json(dict(data.data))
          except:
            await websocket.send_json({ "error": "failed to receive data" })

    @app.get("/api/logs")
    def get_logs(req: Request):
      q = SystemLogQueryParams.model_validate(req.query_params)
      if q.offset == 0: return self.log_handler.log_entries[-q.count:]
      else: return self.log_handler.log_entries[-q.offset-q.count:-q.offset]

    @app.get("/api/dashboards")
    def list_dashboards(): return self.dashboards.dashboards

    @app.get("/api/task-templates")
    def list_task_factories(): return self.task_factories.task_templates

    @app.get("/api/deployments")
    def list_deployments(): return self.deployments.deployments

    @app.post("/api/deployment")
    async def create_deployment(tasks: list[DeploymentTask] = []):
      deployment = Deployment(tasks=tasks)
      self.deployments.store_deployment(deployment)
      return deployment

    @app.get("/api/deployment/{id}")
    async def get_deployment(id: str):
      deployment = self.deployments.get_deployment(id)
      if deployment is None: self._deployment_not_found(id)
      return deployment

    @app.get("/api/deployment/{id}/started")
    def get_started_deployment(id: str): 
      deployment = self.deployments.get_started_deployment(id)
      if deployment is None: raise HTTPException(status_code=404, detail=f"Started deployment with id {id} not found! Maybe it hasn't been started yet?")
      return deployment

    @app.put("/api/deployment")
    async def update_deployment(deployment: Deployment):
      if not self.deployments.has_deployment(deployment.id): self._deployment_not_found(deployment.id)
      deployment.status = "offline"
      self.deployments.store_deployment(deployment)
      return deployment

    @app.delete("/api/deployment/{id}")
    async def delete_deployment(id: str):
      if not self.deployments.has_deployment(id): self._deployment_not_found(id)
      if self.deployments.deployment_was_started(id): raise HTTPException(status_code=400, detail="deployment is running")
      self.deployments.remove_deployment(id)
      return { "success": True }

    @app.get("/api/deployment/{id}/status")
    def get_deployment_status(id: str): return self._respond_deployment_status(id)

    @app.post("/api/deployment/{id}/stop")
    async def stop_deployment(id: str):
      deployment = self.deployments.get_started_deployment(id)
      if deployment is None: self._deployment_not_found(id)
      asyncio.create_task(self.stop_deployment(client, deployment))
      await asyncio.sleep(0.1)
      return self._respond_deployment_status(id)

    @app.post("/api/deployment/{id}/start")
    async def start_deployment(id: str):
      deployment = self.deployments.get_deployment(id)
      if deployment is None: self._deployment_not_found(id)
      if self.deployments.deployment_was_started(id): raise HTTPException(status_code=400, detail="deployment already started")
      await self._assign_topic_ids(client, deployment)
      asyncio.create_task(self.start_deployment(client, self.deployments.set_deployment_started(deployment)))
      await asyncio.sleep(0.1)
      return self._respond_deployment_status(id)

    app.mount("/", SPAStaticFiles(directory="./web/dist", html=True))
    
    await self.asgi_server.serve(app)

  async def _assign_topic_ids(self, client: Client, deployment: Deployment):
    topic_str_ids = set(itertools.chain.from_iterable(task.get_topic_ids() for task in deployment.tasks))
    topic_int_ids = await client.request_topic_ids(len(topic_str_ids))
    topic_id_map = { topic_str_id: topic_int_id for topic_str_id, topic_int_id in zip(topic_str_ids, topic_int_ids) }
    self.topic_id_map.update(topic_id_map)
    for task in deployment.tasks:
      task.topic_id_map = { k: topic_id_map[k] for k in set(task.get_topic_ids()) }

  def _deployment_not_found(self, id: str): raise HTTPException(status_code=404, detail=f"Deployment with id {id} not found!")
  def _respond_deployment_status(self, id: str):
    try: return self.deployments.get_deployment_status(id)
    except: self._deployment_not_found(id)

  async def _stop_task_deployments(self, client: Client, tasks: list[DeploymentTask]):
    async def delete_task(task: DeploymentTask):
      try:
        status = await self.task_factories.delete_task(task.task_factory_id, task.id)
        status.validate_running(False)
      except Exception as e:
        logging.error(f"failed to stop deployment {task.id}: {e}")
        raise e
    try:
      await asyncio.wait([ asyncio.create_task(delete_task(task)) for task in tasks ])
    except Exception as e:
      logging.error(f"failed to stop deployment: {e}")
  
  async def stop_deployment(self, client: Client, deployment: Deployment):
    deployment.status = "stopping"
    await self._stop_task_deployments(client, deployment.tasks)
    self.deployments.set_deployment_stopped(deployment)

  async def start_deployment(self, client: Client, deployment: Deployment):
    deployment.status = "starting"
    deployed_tasks = []
    deployment_failed = False

    async def deploy_task(task: DeploymentTask):
      nonlocal deployment_failed
      try:
        status = await self.task_factories.start_task(task)
        status.validate_running(True)
        deployed_tasks.append(task)
      except Exception as e:
        deployment_failed = True
        logging.error(f"failed to deploy task {task.id}: {e}")
        return

    await asyncio.wait([ asyncio.create_task(deploy_task(task)) for task in deployment.tasks ])
    if deployment_failed:
      deployment.status = "failed"
    else:
      deployment.status = "running"