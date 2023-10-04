import hashlib
import socket
import struct
from typing import Any, ClassVar, Optional, Union

from fastapi import FastAPI
from streamtasks.asgi import ASGIAppRunner
from streamtasks.client.fetch import FetchRequest, FetchServer
from streamtasks.net import Link
from streamtasks.helpers import INSTANCE_ID
from streamtasks.message.data import SerializableData
from streamtasks.system.protocols import AddressNames, WorkerTopics
from streamtasks.system.types import DeploymentTask, DeploymentTaskScaffold, RPCUIEventRequest, RPCUIEventResponse, RPCTaskConnectRequest, RPCTaskConnectResponse, TaskDeploymentDeleteMessage, TaskStatus, TaskFactoryRegistration, TaskFetchDescriptors
from streamtasks.system.helpers import asgi_app_not_found
from abc import ABC, abstractclassmethod, abstractmethod, abstractproperty
import asyncio

from streamtasks.client import Client
from streamtasks.worker import Worker

class Task(ABC):
  def __init__(self, client: Client):
    self.client = client
    self._task = None
    self.app = asgi_app_not_found

  def get_deployment_status(self) -> TaskStatus: 
    error = None if self._task is None or not self._task.done() else self._task.exception()
    return TaskStatus(
      running=self._task is not None and not self._task.done(),
      error=str(error) if error is not None else None)

  async def stop(self, timeout: float = None): 
    if self._task is None: raise RuntimeError("Task not started")
    self._task.cancel()
  async def start(self):
    if self._task is not None: raise RuntimeError("Task already started")
    self._task = asyncio.create_task(self.start_task())

  @abstractmethod
  async def start_task(self): pass

class TaskFactoryWorker(Worker, ABC):
  registered_ids: ClassVar[set[str]] = set()
  
  def __init__(self, node_link: Link):
    super().__init__(node_link)
    
    self.id = self._generate_id()
    TaskFactoryWorker.registered_ids.add(self.id)
    
    self.tasks = {}
    self.setup_done = asyncio.Event()
    self.web_server_running = asyncio.Event()
    self.fetch_server_running = asyncio.Event()
    self.stop_timeout = 2
    self._client = None
    self._task_startup_duration = 0.1
  
  @property
  def name(self): return self.__class__.__name__
 
  async def start(self):
    try:
      self._client = Client(await self.create_link())
      await asyncio.gather(
        self._setup(),
        self._run_fetch_server(),
        self._run_web_server(),
        super().start()
      )
    finally:
      self.web_server_running.clear()
      self.fetch_server_running.clear()
      self.setup_done.clear()
      for task in self.tasks.values(): await task.stop(self.stop_timeout)

  async def _setup(self):
    await self.connected.wait()
    await self._client.wait_for_topic_signal(WorkerTopics.DISCOVERY_SIGNAL)
    await self._client.request_address()
    await self._client.wait_for_address_name(AddressNames.TASK_MANAGER)
    self.reg = TaskFactoryRegistration(
      id=self.id, 
      worker_address=self._client.address,
      task_template=self.task_template.model_dump()
    )
    await self._client.fetch(AddressNames.TASK_MANAGER, TaskFetchDescriptors.REGISTER_TASK_FACTORY, self.reg.model_dump())
    self.setup_done.set()

  async def _run_fetch_server(self):
    await self.setup_done.wait()

    server = FetchServer(self._client)

    @server.route(TaskFetchDescriptors.DELETE_TASK)
    async def delete_task(req: FetchRequest):
      deployment: TaskDeploymentDeleteMessage = TaskDeploymentDeleteMessage.model_validate(req.body)
      status = await self.delete_task(deployment)
      await req.respond(status.model_dump())

    @server.route(TaskFetchDescriptors.DEPLOY_TASK)
    async def deploy_task(req: FetchRequest):
      deployment: DeploymentTask = DeploymentTask.model_validate(req.body)
      status = await self.deploy_task(deployment)
      await req.respond(status.model_dump())

    self.fetch_server_running.set()
    await server.start()

  async def _run_web_server(self):
    await self.setup_done.wait()

    app = FastAPI()

    @app.post("/rpc/connect")
    async def rpc_connect(req: RPCTaskConnectRequest):
      try:
        deployment = await self.rpc_connect(req)
        if deployment is None: raise Exception("Something went wrong!")
        return RPCTaskConnectResponse(task=deployment, error_message=None)
      except Exception as e:
        return RPCTaskConnectResponse(task=None, error_message=str(e))
      
    @app.post("/rpc/ui-event")
    async def rpc_ui_event(req: RPCUIEventRequest):
      res = await self.rpc_ui_event(req)
      return RPCUIEventResponse.model_validate(res)
    
    runner = ASGIAppRunner(self._client, app, self.reg.worker_address)
    self.web_server_running.set()
    await runner.start()

  async def wait_idle(self):
    await self.web_server_running.wait()
    await self.fetch_server_running.wait()

  async def delete_task(self, deployment: TaskDeploymentDeleteMessage):
    if deployment.id not in self.tasks: return
    task: Task = self.tasks[deployment.id]
    await task.stop(self.stop_timeout)
    del self.tasks[deployment.id]
    return task.get_deployment_status()
  
  async def deploy_task(self, deployment: DeploymentTask):
    if deployment.id in self.tasks:
      task: Task = self.tasks[deployment.id]
      if task.can_update(deployment): 
        await task.update(deployment)
        await asyncio.sleep(self._task_startup_duration)
        return task.get_deployment_status()
      else: await task.stop(self.stop_timeout)
    task = await self.create_task(deployment)
    await task.start()
    self.tasks[deployment.id] = task
    await asyncio.sleep(self._task_startup_duration)
    return task.get_deployment_status()
  
  async def create_client(self) -> Client: return Client(await self.create_link())
  
  @property
  def hostname(self): return socket.gethostname()
  
  @abstractproperty
  def task_template(self) -> DeploymentTask: pass
  @abstractmethod
  async def rpc_connect(self, req: RPCTaskConnectRequest) -> Optional[DeploymentTask]: pass
  async def rpc_ui_event(self, req: RPCUIEventRequest) -> RPCUIEventResponse: return RPCUIEventResponse(task=req.task)
  @abstractmethod
  async def create_task(self, deployment: DeploymentTask) -> Task: pass
  
  def _generate_id(self):
    counter = 0
    while True:
      h = hashlib.sha256()
      h.update(self.name.encode("utf-8"))
      h.update(str(INSTANCE_ID.value).encode("utf-8"))
      h.update(struct.pack("<Q", counter))
      wid = h.hexdigest()
      if wid not in TaskFactoryWorker.registered_ids: break
      counter += 1
    return wid
