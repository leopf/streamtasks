from enum import Enum
import hashlib
import mimetypes
from typing import Any, Iterable, Optional
from uuid import UUID, uuid4
from pydantic import UUID4, BaseModel, Field, TypeAdapter, ValidationError, field_serializer
from abc import ABC, abstractmethod
from streamtasks.asgi import ASGIAppRunner, ASGIProxyApp
from streamtasks.asgiserver import ASGIHandler, ASGIRouter, ASGIServer, HTTPContext, TransportContext, decode_data_uri, http_context_handler, path_rewrite_handler, static_content_handler, static_files_handler, transport_context_handler
from streamtasks.client import Client
import asyncio
from streamtasks.client.broadcast import BroadcastReceiver, BroadcastingServer
from streamtasks.client.discovery import register_address_name
from streamtasks.client.fetch import FetchRequest, FetchServer, new_fetch_body_bad_request, new_fetch_body_general_error
from streamtasks.client.signal import SignalServer, send_signal
from streamtasks.net import DAddress, EndpointOrAddress, Link, Switch
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.types import Message, TopicDataMessage
from streamtasks.net.utils import str_to_endpoint
from streamtasks.services.protocols import AddressNames
from streamtasks.utils import NODE_NAME
from streamtasks.worker import Worker

MetadataDict = dict[str, int|float|str|bool]

class Task(ABC):
  def __init__(self, client: Client):
    self.client = client
    self._task = None
  async def setup(self) -> dict[str, Any]: return {}
  @abstractmethod
  async def run(self): pass

class ModelWithId(BaseModel):
  id: UUID4
  
  @field_serializer("id")
  def serialize_id(self, id: UUID4): return str(id)

class ModelWithStrId(BaseModel):
  id: str

class TaskStartRequest(ModelWithId):
  report_address: int
  config: Any

class TaskStartResponse(ModelWithId):
  error: Optional[str]
  metadata: MetadataDict

TaskCancelRequest = ModelWithId
  
class TaskStatus(Enum):
  starting = 0
  running = 1
  stopped = 2
  ended = 3
  failed = 4
  
  @property
  def is_active(self): return self in { TaskStatus.running, TaskStatus.starting }
  
class TaskReport(ModelWithId):
  error: Optional[str]
  status: TaskStatus

class TaskHostRegistration(ModelWithStrId):
  address: int
  metadata: MetadataDict
  
TaskHostRegistrationList = TypeAdapter(list[TaskHostRegistration])

class TMTaskStartRequest(BaseModel):
  host_id: str
  config: Any

TMTaskRequestBase = ModelWithId

class TaskInstance(ModelWithId):
  host_id: str
  config: Any
  metadata: MetadataDict
  error: Optional[str]
  status: TaskStatus

class TASK_CONSTANTS:
  # fetch descriptors
  FD_REGISTER_TASK_HOST = "register_task_host"
  FD_TM_LIST_TASK_HOSTS = "list_task_hosts"
  FD_TM_GET_TASK_HOST = "get_task_host"
  
  FD_TM_GET_TASK = "get_task"
  FD_TM_TASK_START = "start_task"
  FD_TM_TASK_CANCEL = "cancel_task"
  
  FD_TASK_START = "start"
  FD_TASK_CANCEL = "cancel"
  
  # signal descriptors
  SD_TM_TASK_REPORT = "report_task_status"
  SD_UNREGISTER_TASK_HOST = "unregister_task_host"

class MetadataFields:
  ASGISERVER = "asgiserver"

class TaskHost(Worker):
  def __init__(self, node_link: Link, switch: Switch | None = None, register_endpoits: list[EndpointOrAddress] = []):
    super().__init__(node_link, switch)
    self.client: Client
    self.tasks: dict[str, asyncio.Task] = {}
    self.ready = asyncio.Event()
    self.register_endpoits = register_endpoits
    
    id_hash = hashlib.sha256()
    id_hash.update(b"TaskHost")
    id_hash.update(self.__class__.__name__.encode("utf-8"))
    id_hash.update(NODE_NAME.encode("utf-8"))
    self.id = id_hash.hexdigest()[:16]
  
  @property
  def metadata(self) -> MetadataDict: return {}

  async def register(self, endpoint: EndpointOrAddress) -> TaskHostRegistration:
    if not hasattr(self, "client"): raise ValueError("Client not created yet!")
    if self.client.address is None: raise ValueError("Client had no address!")
    registration = TaskHostRegistration(id=self.id, address=self.client.address, metadata={ **self.metadata, "nodename": NODE_NAME })
    await self.client.fetch(endpoint, TASK_CONSTANTS.FD_REGISTER_TASK_HOST, registration.model_dump())
    # TODO store info for unregister
    return registration
  
  async def unregister(self, address: DAddress, registration_id: str):
    # TODO: kills tasks under this reg
    await send_signal(self.client, address, TASK_CONSTANTS.SD_UNREGISTER_TASK_HOST, ModelWithStrId(id=registration_id).model_dump())

  async def run(self):
    try:
      await self.setup()
      self.client = await self.create_client()
      self.client.start()
      await self.client.request_address()
      self.ready.set()
      for register_ep in self.register_endpoits: await self.register(register_ep)
      await asyncio.gather(self.run_api())
    finally:
      # TODO: unregister all
      for task in self.tasks.values(): task.cancel()
      if len(self.tasks) > 0: await asyncio.wait(self.tasks.values(), timeout=1) # NOTE: make configurable
      await self.shutdown()
      self.ready.clear()
    
  @abstractmethod
  async def create_task(self, config: Any) -> Task: pass
  async def run_task(self, id: UUID4, task: Task, report_address: int):
    error_text = None
    status = TaskStatus.running
    try:
      await task.run()
      status = TaskStatus.ended
    except asyncio.CancelledError: status = TaskStatus.stopped
    except BaseException as e:
      status = TaskStatus.failed
      error_text = str(e)
    
    await send_signal(self.client, report_address, TASK_CONSTANTS.SD_TM_TASK_REPORT, TaskReport(id=id, status=status, error=error_text).model_dump())
    self.tasks.pop(id, None)
    
  async def run_api(self):
    fetch_server = FetchServer(self.client)
    
    @fetch_server.route(TASK_CONSTANTS.FD_TASK_START)
    async def _(req: FetchRequest):
      body = TaskStartRequest.model_validate(req.body)
      try:
        task = await self.create_task(body.config)
        metadata = await asyncio.wait_for(task.setup(), 1) # NOTE: make this configurable
        self.tasks[body.id] = asyncio.create_task(self.run_task(body.id, task, body.report_address))
        await req.respond(TaskStartResponse(id=body.id, metadata=metadata, error=None))
      except BaseException as e:
        await req.respond(TaskStartResponse(id=body.id, error=str(e), metadata={}))
    
    @fetch_server.route(TASK_CONSTANTS.FD_TASK_CANCEL)
    async def _(req: FetchRequest):
      body = TaskCancelRequest.model_validate(req.body)
      try:
        task = self.tasks[body.id]
        task.cancel("Cancelled remotely!")
        await req.respond("OK")
      except KeyError as e: await req.respond_error(new_fetch_body_bad_request(str(e)))
      except BaseException as e: await req.respond_error(new_fetch_body_general_error(str(e)))
      
    await fetch_server.run()

def get_namespace_by_task_id(task_id: UUID4): return f"/task/{task_id}"

class TaskManager(Worker):
  def __init__(self, node_link: Link, switch: Switch | None = None, address_name: str = AddressNames.TASK_MANAGER):
    super().__init__(node_link, switch)
    self.task_hosts: dict[str, TaskHostRegistration] = {}
    self.tasks: dict[UUID4, TaskInstance] = {}
    self.address_name = address_name
    self.client: Client
    self.bc_server: BroadcastingServer
  
  async def run(self):
    try:
      await self.setup()
      self.client = await self.create_client()
      self.client.start()
      await self.client.request_address()
      await register_address_name(self.client, self.address_name)
      self.bc_server = BroadcastingServer(self.client)
      await asyncio.gather(
        self.run_fetch_api(),
        self.run_signal_api(),
        self.bc_server.run()
      )
    finally: 
      await self.shutdown()
  
  async def run_signal_api(self):
    server = SignalServer(self.client)
    
    @server.route(TASK_CONSTANTS.SD_TM_TASK_REPORT)
    async def _(message_data: Any):
      report = TaskReport.model_validate(message_data)
      task = self.tasks[report.id]
      task.status = report.status
      task.error = report.error
      if task.status is not TaskStatus.running: self.tasks.pop(task.id, None)
      await self.bc_server.broadcast(get_namespace_by_task_id(task.id), MessagePackData(task.model_dump()))
  
    @server.route(TASK_CONSTANTS.SD_UNREGISTER_TASK_HOST)
    async def _(message_data: Any):
      data = ModelWithStrId.model_validate(message_data)
      self.task_hosts.pop(data.id, None)
      self.tasks = { tid: task for tid, task in self.tasks.items() if task.host_id != data.id }

    await server.run()
  
  async def run_fetch_api(self):
    server = FetchServer(self.client)
    
    @server.route(TASK_CONSTANTS.FD_REGISTER_TASK_HOST)
    async def _(req: FetchRequest):
      try:
        reg = TaskHostRegistration.model_validate(req.body)
        self.task_hosts[reg.id] = reg
        await req.respond(None)
      except (ValidationError, KeyError) as e: await req.respond_error(new_fetch_body_bad_request(str(e)))
      
    @server.route(TASK_CONSTANTS.FD_TM_LIST_TASK_HOSTS) 
    async def _(req: FetchRequest): await req.respond(TaskHostRegistrationList.dump_python(list(self.task_hosts.values())))
      
    @server.route(TASK_CONSTANTS.FD_TM_GET_TASK_HOST) 
    async def _(req: FetchRequest):
      try:
        id = ModelWithStrId.model_validate(req.body).id
        await req.respond(self.task_hosts[id].model_dump())
      except (ValidationError, KeyError) as e: await req.respond_error(new_fetch_body_bad_request(str(e)))

    @server.route(TASK_CONSTANTS.FD_TM_GET_TASK)
    async def _(req: FetchRequest):
      try:
        body = ModelWithId.model_validate(req.body)
        await req.respond(self.tasks[body.id].model_dump())
      except (ValidationError, KeyError) as e: await req.respond_error(new_fetch_body_bad_request(str(e)))
    
    @server.route(TASK_CONSTANTS.FD_TM_TASK_START)
    async def _(req: FetchRequest):
      try:
        body = TMTaskStartRequest.model_validate(req.body)
        task_host = self.task_hosts[body.host_id]
        
        th_req = TaskStartRequest(
          id=uuid4(),
          report_address=self.client.address,
          config=body.config
        )
        
        inst = TaskInstance(
          id= th_req.id,
          host_id=body.host_id,
          config=body.config,
          metadata={},
          error=None,
          status=TaskStatus.starting
        )
        self.tasks[inst.id] = inst
        
        task_start_result = await self.client.fetch(task_host.address, TASK_CONSTANTS.FD_TASK_START, th_req.model_dump())
        task_start_result: TaskStartResponse = TaskStartResponse.model_validate(task_start_result)
        
        inst.metadata=task_start_result.metadata
        inst.error=task_start_result.error
        inst.status=TaskStatus.running if task_start_result.error is None else TaskStatus.failed
        
        await req.respond(inst.model_dump())
      except (ValidationError, KeyError) as e: await req.respond_error(new_fetch_body_bad_request(str(e)))
    
    @server.route(TASK_CONSTANTS.FD_TM_TASK_CANCEL)
    async def _(req: FetchRequest):
      try:
        body = TMTaskRequestBase.model_validate(req.body)
        task_inst = self.tasks[body.id]
        task_host = self.task_hosts[task_inst.host_id]
        tc_req = TaskCancelRequest(id=task_inst.id)
        task_cancel_result = await self.client.fetch(task_host.address, TASK_CONSTANTS.FD_TASK_CANCEL, tc_req.model_dump())
        if task_cancel_result != "OK": raise Exception("Failed to cancel task!")
        await req.respond("OK")
      except (ValidationError, KeyError) as e: await req.respond_error(new_fetch_body_bad_request(str(e)))

    await server.run()

class TaskBroadcastReceiver(BroadcastReceiver):
  def __init__(self, client: Client, namespaces: Iterable[str], endpoint: str | int | tuple[str | int, int]):
    super().__init__(client, namespaces, endpoint)
    self._recv_queue: asyncio.Queue[TaskInstance]
  async def get(self) -> TaskInstance: return await super().get()
  def on_message(self, message: Message):
    if isinstance(message, TopicDataMessage) and message.topic in self._topics_ns_map:
      try: self._recv_queue.put_nowait(TaskInstance.model_validate(message.data.data))
      except ValidationError as e: pass 
  
class TaskManagerClient:
  def __init__(self, client: Client, address_name: str = AddressNames.TASK_MANAGER) -> None:
    self.address_name = address_name
    self.client = client

  async def list_task_hosts(self):
    result = await self.client.fetch(self.address_name, TASK_CONSTANTS.FD_TM_LIST_TASK_HOSTS, None)
    return TaskHostRegistrationList.validate_python(result)
  async def get_task_host(self, id: str):
    result = await self.client.fetch(self.address_name, TASK_CONSTANTS.FD_TM_GET_TASK_HOST, ModelWithStrId(id=id).model_dump())
    return TaskHostRegistration.model_validate(result)
  async def get_task(self, id: UUID4):
    result = await self.client.fetch(self.address_name, TASK_CONSTANTS.FD_TM_GET_TASK, ModelWithId(id=id).model_dump())
    return TaskInstance.model_validate(result)
  async def start_task(self, host_id: str, config: Any):
    result = await self.client.fetch(self.address_name, TASK_CONSTANTS.FD_TM_TASK_START, TMTaskStartRequest(host_id=host_id, config=config).model_dump())
    return TaskInstance.model_validate(result)
  async def cancel_task(self, task_id: UUID4):
    await self.client.fetch(self.address_name, TASK_CONSTANTS.FD_TM_TASK_CANCEL, TMTaskRequestBase(id=task_id).model_dump()) 
  async def cancel_task_wait(self, task_id: UUID4):
    async with self.task_message_receiver([ task_id ]) as receiver:
      await self.cancel_task(task_id)
      while True:
        task_instance = await receiver.get()
        if not task_instance.status.is_active: return task_instance
  
  def task_message_receiver(self, task_ids: Iterable[UUID4]): return TaskBroadcastReceiver(self.client, [ get_namespace_by_task_id(task_id) for task_id in task_ids ], self.address_name)

class Deployment(ModelWithId):
  id: UUID4 = Field(default_factory=uuid4)
  label: str
  
class StoredTaskInstance(ModelWithId):
  deployment_id: UUID4
  task_host_id: str
  config: dict[str, Any]
  frontendConfig: dict[str, Any]
  inputs: list[MetadataDict]
  outputs: list[MetadataDict]

DeploymentList = TypeAdapter(list[Deployment])

class TaskManagerWeb(Worker):
  def __init__(self, node_link: Link, switch: Switch | None = None, address_name: str = AddressNames.TASK_MANAGER_WEB, 
               task_manager_address_name: str = AddressNames.TASK_MANAGER, public_path: str | None = None):
    super().__init__(node_link, switch)
    self.task_manager_address_name = task_manager_address_name
    self.address_name = address_name
    self.task_host_asgi_handlers: dict[str, ASGIHandler] = {}
    self.task_asgi_handlers: dict[UUID4, ASGIHandler] = {}
    self.public_path = public_path
    self.deployments_store: dict[str, str] = {}
    self.tasks_store: dict[str, str] = {}
    self.client: Client
    self.tm_client: TaskManagerClient
  
  async def run(self):
    try:
      await self.setup()
      self.client = await self.create_client()
      self.client.start()
      await self.client.request_address()
      await register_address_name(self.client, self.address_name)
      self.tm_client = TaskManagerClient(self.client, self.task_manager_address_name)
      await asyncio.gather(self.run_asgi_server())
    finally:
      await self.shutdown()
      
  async def run_asgi_server(self):
    app = ASGIServer()
    
    @app.handler
    @http_context_handler
    async def _error_handler(ctx: HTTPContext):
      try:
        await ctx.next()
      except (ValidationError, KeyError, ValueError) as e:
        await ctx.respond_text(str(e), 400)
      except BaseException as e:
        await ctx.respond_text(str(e), 500)
        
    
    router = ASGIRouter()
    app.add_handler(router)
    
    @router.get("/api/task-hosts")
    @http_context_handler
    async def _(ctx: HTTPContext): 
      await ctx.respond_json_raw(TaskHostRegistrationList.dump_json(await self.tm_client.list_task_hosts()))
    
    @router.post("/api/task/start")
    @http_context_handler
    async def _(ctx: HTTPContext):
      req = TMTaskStartRequest(**(await ctx.receive_json()))
      task_instance = await self.tm_client.start_task(req.host_id, req.config)
      await ctx.respond_json_string(task_instance.model_dump_json())
    
    @router.post("/api/task/stop/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      id = UUID(ctx.params.get("id", ""))
      task_instance = await self.tm_client.cancel_task_wait(id)
      await ctx.respond_json_string(task_instance.model_dump_json())
    
    @router.post("/api/task/cancel/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      id = UUID(ctx.params.get("id", ""))
      await self.tm_client.cancel_task(id)
      await ctx.respond_status(200)

    @router.get("/api/deployments")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json_raw(DeploymentList.dump_json([ Deployment.model_validate_json(d) for d in self.deployments_store.values() ]))
    
    @router.post("/api/deployment")
    @http_context_handler
    async def _(ctx: HTTPContext): 
      data = Deployment.model_validate_json(await ctx.receive_json_raw())
      self.deployments_store[str(data.id)] = data.model_dump_json()
      await ctx.respond_json_string(self.deployments_store[str(data.id)])
    
    @router.put("/api/deployment")
    @http_context_handler
    async def _(ctx: HTTPContext):
      data = Deployment.model_validate_json(await ctx.receive_json_raw())
      self.deployments_store[str(data.id)] = data.model_dump_json()
      await ctx.respond_json_string(self.deployments_store[str(data.id)])
    
    @router.delete("/api/deployment/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      if self.deployments_store.pop(ctx.params["id"], None) is None: await ctx.respond_status(400)
      else: await ctx.respond_status(200)
      
    @router.get("/api/deployment/{id}/tasks")
    @http_context_handler
    async def _(ctx: HTTPContext):
      deployment_id = UUID(hex=ctx.params.get("id"))
      return (task for task in (StoredTaskInstance.model_validate_json(v) for v in self.tasks_store.values()) if task.deployment_id == deployment_id)
    
    @router.delete("/api/task/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      if self.tasks_store.pop(ctx.params["id"], None) is None: await ctx.respond_status(400)
      else: await ctx.respond_status(200)
      
    @router.put("/api/task")
    @http_context_handler
    async def _(ctx: HTTPContext):
      data = StoredTaskInstance.model_validate_json(await ctx.receive_json_raw())
      self.tasks_store[str(data.id)] = data.model_dump_json()  
      await ctx.respond_json_string(data.model_dump_json())

    @router.post("/api/deployment/{*}")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_status(200)
    
    # TODO: lifecycle api support
    @router.transport_route("/task/{id}/{path*}")
    @path_rewrite_handler("/{path*}")
    @transport_context_handler
    async def _(ctx: TransportContext):
      id: UUID4 = UUID(ctx.params.get("id", ""))
      await ctx.delegate(await self.get_task_asgi_handler(id))

    # TODO: lifecycle api support
    @router.transport_route("/task-host/{id}/{path*}")
    @path_rewrite_handler("/{path*}")
    @transport_context_handler
    async def _(ctx: TransportContext):
      id = ctx.params.get("id", "")
      await ctx.delegate(await self.get_task_host_asgi_handler(id))
        
    if self.public_path is not None: router.add_handler(static_files_handler(self.public_path, ["index.html"]))
    
    runner = ASGIAppRunner(self.client, app)
    await runner.run()
    
  async def get_task_host_asgi_handler(self, id: str) -> ASGIHandler:
    if (router := self.task_host_asgi_handlers.get(id, None)) is None:
      reg: TaskHostRegistration = await self.tm_client.get_task_host(id)
      self.task_host_asgi_handlers[id] = router = self._metadata_to_router(reg.metadata)
    return router

  async def get_task_asgi_handler(self, id: UUID4) -> ASGIHandler:
    if (router := self.task_asgi_handlers.get(id, None)) is None:
      reg: TaskInstance = await self.tm_client.get_task(id)
      self.task_asgi_handlers[id] = router = self._metadata_to_router(reg.metadata)
    return router
  
  def _metadata_to_router(self, metadata: MetadataDict) -> ASGIHandler:
    router = ASGIRouter()
    for (path, content) in ((k[5:], v) for k, v in metadata.items() if isinstance(v, str) and k.lower().startswith("file:")):
      guessed_mime_type = mimetypes.guess_type(path)[0]
      if content.startswith("data:"):
        # TODO: better validation
        data, mime_type, charset = decode_data_uri(content, (guessed_mime_type,)*2)
        router.add_http_route(static_content_handler(data, mime_type, charset), path, { "get" })
      else:
        router.add_http_route(static_content_handler(content.encode("utf-8"), guessed_mime_type or "text/plain"), path, { "get" })
    if MetadataFields.ASGISERVER in metadata:
      router.add_handler(ASGIProxyApp(self.client, str_to_endpoint(metadata[MetadataFields.ASGISERVER])))
    return router