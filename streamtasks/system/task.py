from enum import Enum
import gc
import logging
import threading
from typing import Any, AsyncContextManager, Iterable, Optional
from uuid import uuid4
from pydantic import UUID4, BaseModel, TypeAdapter, ValidationError, field_serializer
from abc import ABC, abstractmethod
from streamtasks.asgi import ASGIAppRunner, asgi_default_http_error_handler
from streamtasks.asgiserver import ASGIRouter, ASGIServer
from streamtasks.client import Client
import asyncio
from streamtasks.client.broadcast import BroadcastReceiver, BroadcastingServer
from streamtasks.client.discovery import address_name_context, get_topic_space, wait_for_topic_signal
from streamtasks.client.fetch import FetchError, FetchErrorStatusCode, FetchRequest, FetchServer, new_fetch_body_bad_request, new_fetch_body_general_error, new_fetch_body_not_found
from streamtasks.client.signal import SignalServer, send_signal
from streamtasks.client.topic import OutTopic
from streamtasks.net import EndpointOrAddress, Link, TopicRemappingLink, create_queue_connection
from streamtasks.net.serialization import RawData
from streamtasks.net.utils import endpoint_to_str
from streamtasks.services.constants import NetworkAddressNames, NetworkPorts, NetworkTopics
from streamtasks.env import NODE_NAME
from streamtasks.utils import get_node_name_id
from streamtasks.worker import Worker

MetadataDict = dict[str, int|float|str|bool]

class Task(ABC):
  def __init__(self, client: Client):
    self.client = client
    self._task = None
  async def setup(self) -> dict[str, Any]: return {}
  @abstractmethod
  async def run(self): pass

class SyncTask(Task):
  def __init__(self, client: Client):
    super().__init__(client)
    self.loop = asyncio.get_running_loop()
    self.stop_event = threading.Event()

  async def run(self):
    fut: None | asyncio.Future = None
    async with self.init():
      try:
        fut = self.loop.run_in_executor(None, self.run_sync)
        await asyncio.shield(fut)
      finally:
        self.stop_event.set()
        if fut: await fut

  @abstractmethod
  async def init(self) -> AsyncContextManager: pass

  @abstractmethod
  def run_sync(self): pass

  def send_data(self, topic: OutTopic, data: RawData): asyncio.run_coroutine_threadsafe(topic.send(data), self.loop)

class ModelWithId(BaseModel):
  id: UUID4

  @field_serializer("id")
  def serialize_id(self, id: UUID4): return str(id)

class ModelWithStrId(BaseModel):
  id: str

class TaskStartRequest(ModelWithId):
  report_address: int
  topic_space_id: int | None = None
  config: Any

class TaskStartResponse(ModelWithId):
  error: Optional[str]
  metadata: MetadataDict

TaskCancelRequest = ModelWithId

class TaskStatus(Enum):
  scheduled = "scheduled"
  running = "running"
  stopped = "stopped"
  ended = "ended"
  failed = "failed"

  @property
  def is_active(self): return self in { TaskStatus.running, TaskStatus.scheduled }

class TaskReport(ModelWithId):
  error: Optional[str]
  status: TaskStatus

  @field_serializer("status")
  def serialize_status(self, status: TaskStatus): return status.value

class TaskHostRegistration(ModelWithStrId):
  address: int
  metadata: MetadataDict

TaskHostRegistrationList = TypeAdapter(list[TaskHostRegistration])

class TMTaskScheduleRequest(BaseModel):
  host_id: str
  topic_space_id: int | None = None

class TMTaskStartRequest(ModelWithId):
  config: Any

TMTaskRequestBase = ModelWithId

class TaskInstance(ModelWithId):
  host_id: str
  topic_space_id: int | None = None
  metadata: MetadataDict
  error: Optional[str]
  status: TaskStatus

  @field_serializer("status")
  def serialize_status(self, status: TaskStatus): return status.value

class TaskConstants:
  # fetch descriptors
  FD_REGISTER_TASK_HOST = "register_task_host"
  FD_TM_LIST_TASK_HOSTS = "list_task_hosts"
  FD_TM_GET_TASK_HOST = "get_task_host"

  FD_TM_TASK_GET = "get_task"
  FD_TM_TASK_SCHEDULE = "schedule_task"
  FD_TM_TASK_START = "start_task"
  FD_TM_TASK_CANCEL = "cancel_task"

  FD_TMW_REGISTER_PATH = "register_path"

  FD_TASK_START = "start"
  FD_TASK_CANCEL = "cancel"

  # signal descriptors
  SD_TMW_UNREGISTER_PATH = "unregister_path"
  SD_TM_TASK_REPORT = "report_task_status"
  SD_UNREGISTER_TASK_HOST = "unregister_task_host"

  # broadaster descriptors
  BC_TASK_HOST_REGISTERED = "/task-host/registered"
  BC_TASK_HOST_UNREGISTERED = "/task-host/unregistered"

class MetadataFields:
  ASGISERVER = "asgiserver"

class TaskNotFoundError(BaseException): pass

def get_namespace_by_task_id(task_id: UUID4): return f"/task/{task_id}"
def task_host_id_from_name(name: str): return get_node_name_id("TaskHost" + name)

class TaskHost(Worker):
  def __init__(self, register_endpoits: list[EndpointOrAddress] = []):
    super().__init__()
    self.client: Client
    self.tasks: dict[str, asyncio.Task] = {}
    self.ready = asyncio.Event()
    self.register_endpoits = list(register_endpoits)
    self.id = task_host_id_from_name(self.__class__.__name__)
    self._base_metadata = { "nodename": NODE_NAME() }
    self._registered_at_endpoints: list[EndpointOrAddress] = []

  @property
  def metadata(self) -> MetadataDict: return {}

  async def create_client(self, topic_space_id: int | None = None) -> Client: return Client(await self.create_link(topic_space_id))
  async def create_link(self, topic_space_id: int | None = None) -> Link:
    a, b = create_queue_connection()
    if topic_space_id is not None:
      topic_map = await get_topic_space(self.client, topic_space_id)
      b = TopicRemappingLink(b, topic_map)
    await self.switch.add_link(a)
    return b

  async def register(self, endpoint: EndpointOrAddress = NetworkAddressNames.TASK_MANAGER):
    if not hasattr(self, "client"): raise ValueError("Client not created yet!")
    if self.client.address is None: raise ValueError("Client had no address!")
    reg = TaskHostRegistration(id=self.id, address=self.client.address, metadata={ **self._base_metadata, **self.metadata })
    await self.client.fetch(endpoint, TaskConstants.FD_REGISTER_TASK_HOST, reg.model_dump())
    self._registered_at_endpoints.append(endpoint)

  async def unregister(self, endpoint: EndpointOrAddress = NetworkAddressNames.TASK_MANAGER):
    self._registered_at_endpoints = [ ep for ep in self._registered_at_endpoints if ep!= endpoint ]
    await send_signal(self.client, endpoint, TaskConstants.SD_UNREGISTER_TASK_HOST, ModelWithStrId(id=self.id).model_dump())

  async def run(self):
    try:
      self.client = await self.create_client()
      self.client.start()
      await wait_for_topic_signal(self.client, NetworkTopics.DISCOVERY_SIGNAL)
      await self.client.request_address()
      futs: list[asyncio.Future] = []

      asgi_router = ASGIRouter()
      await self.register_routes(asgi_router)
      if asgi_router.handler_count > 0:
        app = ASGIServer()
        app.add_handler(asgi_default_http_error_handler)
        app.add_handler(asgi_router)
        self._base_metadata[MetadataFields.ASGISERVER] = endpoint_to_str((self.client.address, NetworkPorts.ASGI))
        futs.append(ASGIAppRunner(self.client, app).run())

      self.ready.set()
      for register_ep in self.register_endpoits: await self.register(register_ep)
      await asyncio.gather(self.run_api(), *futs)
    except asyncio.CancelledError: raise
    except BaseException as e:
      if logging.getLogger().isEnabledFor(logging.DEBUG):
        import traceback
        logging.debug("Failed to register task host!", e, traceback.format_exc())
      raise e
    finally:
      shutdown_tasks: list[asyncio.Task] = list(self.tasks) + [ asyncio.create_task(self.unregister(ep)) for ep in self._registered_at_endpoints ]
      for task in self.tasks.values(): task.cancel()
      if len(shutdown_tasks) > 0: await asyncio.wait(shutdown_tasks, timeout=1) # NOTE: make configurable
      await self.shutdown()
      self.ready.clear()

  async def register_routes(self, router: ASGIRouter): pass
  @abstractmethod
  async def create_task(self, config: Any, topic_space_id: int | None) -> Task: pass
  async def run_task(self, id: UUID4, task: Task, report_address: int):
    error_text = None
    status = TaskStatus.running
    try:
      await task.run()
      status = TaskStatus.ended
    except asyncio.CancelledError: status = TaskStatus.stopped
    except BaseException as e:
      import traceback
      print(traceback.format_exc())
      status = TaskStatus.failed
      error_text = str(e)

    await send_signal(self.client, report_address, TaskConstants.SD_TM_TASK_REPORT, TaskReport(id=id, status=status, error=error_text).model_dump())
    self.tasks.pop(id, None)

  async def run_api(self):
    fetch_server = FetchServer(self.client)

    @fetch_server.route(TaskConstants.FD_TASK_START)
    async def _(req: FetchRequest):
      body = TaskStartRequest.model_validate(req.body)
      try:
        task = await self.create_task(body.config, body.topic_space_id)
        metadata = await asyncio.wait_for(task.setup(), 1) # NOTE: make this configurable
        self.tasks[body.id] = asyncio.create_task(self.run_task(body.id, task, body.report_address))
        await req.respond(TaskStartResponse(id=body.id, metadata=metadata, error=None))
      except BaseException as e:
        await req.respond(TaskStartResponse(id=body.id, error=str(e), metadata={}))

    @fetch_server.route(TaskConstants.FD_TASK_CANCEL)
    async def _(req: FetchRequest):
      body = TaskCancelRequest.model_validate(req.body)
      try:
        task = self.tasks[body.id]
        task.cancel("Cancelled remotely!")
        await req.respond("OK")
      except KeyError as e: await req.respond_error(new_fetch_body_bad_request(str(e)))
      except BaseException as e: await req.respond_error(new_fetch_body_general_error(str(e)))

    await fetch_server.run()

class TaskManager(Worker):
  def __init__(self, address_name: str = NetworkAddressNames.TASK_MANAGER):
    super().__init__()
    self.task_hosts: dict[str, TaskHostRegistration] = {}
    self.tasks: dict[UUID4, TaskInstance] = {}
    self.address_name = address_name
    self.client: Client
    self.bc_server: BroadcastingServer

  async def run(self):
    try:
      self.client = await self.create_client()
      self.client.start()
      await self.client.request_address()
      self.bc_server = BroadcastingServer(self.client)
      async with address_name_context(self.client, self.address_name):
        await asyncio.gather(
          self.run_fetch_api(),
          self.run_signal_api(),
          self.bc_server.run()
        )
    finally:
      await self.shutdown()

  async def run_signal_api(self):
    server = SignalServer(self.client)

    @server.route(TaskConstants.SD_TM_TASK_REPORT)
    async def _(message_data: Any):
      report = TaskReport.model_validate(message_data)
      task = self.tasks[report.id]
      task.status = report.status
      task.error = report.error
      if task.status is not TaskStatus.running:
        self.tasks.pop(task.id, None)
        gc.collect()
      await self.bc_server.broadcast(get_namespace_by_task_id(task.id), RawData(task.model_dump()))

    @server.route(TaskConstants.SD_UNREGISTER_TASK_HOST)
    async def _(message_data: Any):
      data = ModelWithStrId.model_validate(message_data)
      self.task_hosts.pop(data.id, None)
      self.tasks = { tid: task for tid, task in self.tasks.items() if task.host_id != data.id }
      await self.bc_server.broadcast(TaskConstants.BC_TASK_HOST_UNREGISTERED, RawData(data.model_dump()))

    await server.run()

  async def run_fetch_api(self):
    server = FetchServer(self.client)

    @server.route(TaskConstants.FD_REGISTER_TASK_HOST)
    async def _(req: FetchRequest):
      try:
        reg = TaskHostRegistration.model_validate(req.body)
        self.task_hosts[reg.id] = reg
        await self.bc_server.broadcast(TaskConstants.BC_TASK_HOST_REGISTERED, RawData(reg.model_dump()))
        await req.respond(None)
      except KeyError as e: await req.respond_error(new_fetch_body_not_found(str(e)))
      except ValidationError as e: await req.respond_error(new_fetch_body_bad_request(str(e)))

    @server.route(TaskConstants.FD_TM_LIST_TASK_HOSTS)
    async def _(req: FetchRequest): await req.respond(TaskHostRegistrationList.dump_python(list(self.task_hosts.values())))

    @server.route(TaskConstants.FD_TM_GET_TASK_HOST)
    async def _(req: FetchRequest):
      try:
        id = ModelWithStrId.model_validate(req.body).id
        await req.respond(self.task_hosts[id].model_dump())
      except KeyError as e: await req.respond_error(new_fetch_body_not_found(str(e)))
      except ValidationError as e: await req.respond_error(new_fetch_body_bad_request(str(e)))

    @server.route(TaskConstants.FD_TM_TASK_GET)
    async def _(req: FetchRequest):
      try:
        body = ModelWithId.model_validate(req.body)
        await req.respond(self.tasks[body.id].model_dump())
      except KeyError as e: await req.respond_error(new_fetch_body_not_found(str(e)))
      except ValidationError as e: await req.respond_error(new_fetch_body_bad_request(str(e)))


    @server.route(TaskConstants.FD_TM_TASK_SCHEDULE)
    async def _(req: FetchRequest):
      try:
        body = TMTaskScheduleRequest.model_validate(req.body)

        task_instance = TaskInstance(
          id=uuid4(),
          host_id=body.host_id,
          topic_space_id=body.topic_space_id,
          metadata={},
          error=None,
          status=TaskStatus.scheduled
        )
        self.tasks[task_instance.id] = task_instance

        await req.respond(task_instance.model_dump())
      except KeyError as e: await req.respond_error(new_fetch_body_not_found(str(e)))
      except ValidationError as e: await req.respond_error(new_fetch_body_bad_request(str(e)))

    @server.route(TaskConstants.FD_TM_TASK_START)
    async def _(req: FetchRequest):
      try:
        body = TMTaskStartRequest.model_validate(req.body)
        task_instance = self.tasks[body.id]
        task_host = self.task_hosts[task_instance.host_id]

        task_start_request = TaskStartRequest(
          id=task_instance.id,
          topic_space_id=task_instance.topic_space_id,
          report_address=self.client.address,
          config=body.config
        )

        task_start_result = await self.client.fetch(task_host.address, TaskConstants.FD_TASK_START, task_start_request.model_dump())
        task_start_result: TaskStartResponse = TaskStartResponse.model_validate(task_start_result)

        task_instance.metadata=task_start_result.metadata
        task_instance.error=task_start_result.error
        task_instance.status=TaskStatus.running if task_start_result.error is None else TaskStatus.failed

        if task_instance.status == TaskStatus.failed: self.tasks.pop(task_instance.id)

        await req.respond(task_instance.model_dump())
      except KeyError as e: await req.respond_error(new_fetch_body_not_found(str(e)))
      except ValidationError as e: await req.respond_error(new_fetch_body_bad_request(str(e)))

    @server.route(TaskConstants.FD_TM_TASK_CANCEL)
    async def _(req: FetchRequest):
      try:
        body = TMTaskRequestBase.model_validate(req.body)
        task_inst = self.tasks[body.id]
        task_host = self.task_hosts[task_inst.host_id]
        tc_req = TaskCancelRequest(id=task_inst.id)
        task_cancel_result = await self.client.fetch(task_host.address, TaskConstants.FD_TASK_CANCEL, tc_req.model_dump())
        if task_cancel_result != "OK": raise Exception("Failed to cancel task!")
        await req.respond("OK")
      except KeyError as e: await req.respond_error(new_fetch_body_not_found(str(e)))
      except ValidationError as e: await req.respond_error(new_fetch_body_bad_request(str(e)))

    await server.run()

class TaskBroadcastReceiver(BroadcastReceiver[TaskInstance]):
  def transform_data(self, _: str, data: RawData) -> TaskInstance:
    return TaskInstance.model_validate(data.data)

class TaskHostRegisteredReceiver(BroadcastReceiver[TaskHostRegistration]):
  def transform_data(self, _: str, data: RawData) -> TaskInstance:
    return TaskHostRegistration.model_validate(data.data)

class TaskHostUnregisteredReceiver(BroadcastReceiver[ModelWithId]):
  def transform_data(self, _: str, data: RawData) -> ModelWithId:
    return ModelWithId.model_validate(data.data)

class TaskManagerClient:
  def __init__(self, client: Client, address_name: str = NetworkAddressNames.TASK_MANAGER) -> None:
    self.address_name = address_name
    self.client = client

  async def list_task_hosts(self):
    result = await self.client.fetch(self.address_name, TaskConstants.FD_TM_LIST_TASK_HOSTS, None)
    return TaskHostRegistrationList.validate_python(result)
  async def get_task_host(self, id: str):
    result = await self.client.fetch(self.address_name, TaskConstants.FD_TM_GET_TASK_HOST, ModelWithStrId(id=id).model_dump())
    return TaskHostRegistration.model_validate(result)
  async def get_task(self, id: UUID4):
    result = await self.client.fetch(self.address_name, TaskConstants.FD_TM_TASK_GET, ModelWithId(id=id).model_dump())
    return TaskInstance.model_validate(result)
  async def schedule_task(self, host_id: str, topic_space_id: int | None = None):
    result = await self.client.fetch(self.address_name, TaskConstants.FD_TM_TASK_SCHEDULE, TMTaskScheduleRequest(host_id=host_id, topic_space_id=topic_space_id).model_dump())
    return TaskInstance.model_validate(result)
  async def start_task(self, id: UUID4, config: Any):
    result = await self.client.fetch(self.address_name, TaskConstants.FD_TM_TASK_START, TMTaskStartRequest(id=id, config=config).model_dump())
    return TaskInstance.model_validate(result)
  async def schedule_start_task(self, host_id: str, config: Any, topic_space_id: int | None = None):
    task_instance = await self.schedule_task(host_id=host_id, topic_space_id=topic_space_id)
    task_instance = await self.start_task(id=task_instance.id, config=config)
    return task_instance
  async def cancel_task(self, task_id: UUID4):
    await self.client.fetch(self.address_name, TaskConstants.FD_TM_TASK_CANCEL, TMTaskRequestBase(id=task_id).model_dump())
  async def cancel_task_wait(self, task_id: UUID4):
    async with self.task_receiver([ task_id ]) as receiver:
      try:
        await self.cancel_task(task_id)
      except FetchError as e:
        if e.status_code == FetchErrorStatusCode.NOT_FOUND: raise TaskNotFoundError()
        else: raise e
      while True:
        task_instance = await receiver.get()
        if not task_instance.status.is_active: return task_instance

  def task_receiver(self, task_ids: Iterable[UUID4]): return TaskBroadcastReceiver(self.client, [ get_namespace_by_task_id(task_id) for task_id in task_ids ], self.address_name)
  def task_host_registered_receiver(self): return TaskHostRegisteredReceiver(self.client, [TaskConstants.BC_TASK_HOST_REGISTERED], self.address_name)
  def task_host_unregistered_receiver(self): return TaskHostUnregisteredReceiver(self.client, [TaskConstants.BC_TASK_HOST_UNREGISTERED], self.address_name)
