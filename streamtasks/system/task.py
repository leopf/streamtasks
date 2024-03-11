from enum import Enum
from typing import Any, Iterable, Optional
from uuid import uuid4
from pydantic import UUID4, BaseModel, TypeAdapter, ValidationError, field_serializer
from abc import ABC, abstractmethod
from streamtasks.client import Client
import asyncio
from streamtasks.client.broadcast import BroadcastReceiver, BroadcastingServer
from streamtasks.client.discovery import register_address_name
from streamtasks.client.fetch import FetchRequest, FetchServer, new_fetch_body_bad_request, new_fetch_body_general_error
from streamtasks.client.signal import SignalServer, send_signal
from streamtasks.net import DAddress, Link, Switch
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.types import Message, TopicDataMessage
from streamtasks.services.protocols import AddressNames
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

class TaskHostRegistration(ModelWithId):
  address: int
  metadata: MetadataDict
  
TaskHostRegistrationList = TypeAdapter(list[TaskHostRegistration])

class TMTaskStartRequest(BaseModel):
  task_host_id: UUID4
  config: Any
  
  @field_serializer("task_host_id")
  def serialize_task_host_id(self, id: UUID4): return str(id)

TMTaskRequestBase = ModelWithId

class TaskInstance(ModelWithId):
  id: UUID4
  host_id: UUID4
  config: Any
  metadata: MetadataDict
  error: Optional[str]
  status: TaskStatus

class TASK_CONSTANTS:
  # fetch descriptors
  FD_REGISTER_TASK_HOST = "register_task_host"
  FD_LIST_TASK_HOSTS = "list_task_hosts"
  
  FD_TM_TASK_START = "start_task"
  FD_TM_TASK_CANCEL = "cancel_task"
  
  FD_TASK_START = "start"
  FD_TASK_CANCEL = "cancel"
  
  # signal descriptors
  SD_TM_TASK_REPORT = "report_task_status"
  SD_UNREGISTER_TASK_HOST = "unregister_task_host"

class TaskHost(Worker):
  def __init__(self, node_link: Link, switch: Switch | None = None):
    super().__init__(node_link, switch)
    self.client: Client
    self.tasks: dict[str, asyncio.Task] = {}
    self.ready = asyncio.Event()
  
  @property
  def metadata(self) -> MetadataDict: return {}

  async def register(self, address: DAddress) -> TaskHostRegistration:
    if not hasattr(self, "client"): raise ValueError("Client not created yet!")
    if self.client.address is None: raise ValueError("Client had no address!")
    registration = TaskHostRegistration(id=uuid4(), address=self.client.address, metadata=self.metadata)
    await self.client.fetch(address, TASK_CONSTANTS.FD_REGISTER_TASK_HOST, registration.model_dump())
    return registration
  
  async def unregister(self, address: DAddress, registration_id: UUID4):
    # TODO: kills tasks under this reg
    await send_signal(self.client, address, TASK_CONSTANTS.SD_UNREGISTER_TASK_HOST, ModelWithId(id=registration_id).model_dump())

  async def run(self):
    try:
      await self.setup()
      self.client = await self.create_client()
      self.client.start()
      await self.client.request_address()
      self.ready.set()
      await asyncio.gather(self.run_api())
    finally:
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
    self.task_hosts: dict[UUID4, TaskHostRegistration] = {}
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
      data = ModelWithId.model_validate(message_data)
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
      
    @server.route(TASK_CONSTANTS.FD_LIST_TASK_HOSTS) 
    async def _(req: FetchRequest): await req.respond(TaskHostRegistrationList.dump_python(list(self.task_hosts.values())))
      
    @server.route(TASK_CONSTANTS.FD_TM_TASK_START)
    async def _(req: FetchRequest):
      try:
        body = TMTaskStartRequest.model_validate(req.body)
        task_host = self.task_hosts[body.task_host_id]
        
        th_req = TaskStartRequest(
          id=uuid4(),
          report_address=self.client.address,
          config=body.config
        )
        
        inst = TaskInstance(
          id= th_req.id,
          host_id=body.task_host_id,
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
      except BaseException as e: 
        await req.respond_error(new_fetch_body_general_error(str(e)))
    
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
      except BaseException as e: await req.respond_error(new_fetch_body_general_error(str(e)))

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
    result = await self.client.fetch(self.address_name, TASK_CONSTANTS.FD_LIST_TASK_HOSTS, None)
    return TaskHostRegistrationList.validate_python(result)
  async def start_task(self, task_host_id: UUID4, config: Any):
    result = await self.client.fetch(self.address_name, TASK_CONSTANTS.FD_TM_TASK_START, TMTaskStartRequest(task_host_id=task_host_id, config=config).model_dump())
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