from dataclasses import dataclass
import logging
from typing import Any, Optional
from uuid import uuid4

from pydantic import UUID4, BaseModel, TypeAdapter, ValidationError, field_serializer
from streamtasks.asgi import asgi_app_not_found
from abc import ABC, abstractmethod, abstractproperty
from streamtasks.client import Client
import asyncio

from streamtasks.client.fetch import FetchRequest, FetchServer, new_fetch_body_bad_request, new_fetch_body_general_error
from streamtasks.client.receiver import AddressReceiver
from streamtasks.net import Endpoint, Link, Switch
from streamtasks.net.message.data import MessagePackData, SerializableData
from streamtasks.worker import Worker


class Task(ABC):
  def __init__(self, client: Client):
    self.client = client
    self._task = None
  async def setup(self) -> dict[str, Any]: return {}
  @abstractmethod
  async def run(self): pass

class TaskStartRequest(BaseModel):
  id: str
  report_address: int
  config: Any

class TaskCancelRequest(BaseModel):
  id: str

class TaskStartResponse(BaseModel):
  id: str
  error: Optional[str]
  metadata: dict[str, Any]
  
class TaskShutdownReport(BaseModel):
  id: str
  error: Optional[str]

class TaskHostRegistration(BaseModel):
  id: UUID4
  address: int
  metadata: dict[str, Any]
  
  @field_serializer("id")
  def serialize_id(self, id: UUID4): return str(id)
  
TaskHostRegistrationList = TypeAdapter(list[TaskHostRegistration])

class TMTaskStartRequest(BaseModel):
  task_host_id: UUID4
  config: Any
  
  @field_serializer("task_host_id")
  def serialize_task_host_id(self, id: UUID4): return str(id)

class TMTaskRequestBase(BaseModel):
  id: UUID4
  
  @field_serializer("id")
  def serialize_id(self, id: UUID4): return str(id)

class TaskInstance(BaseModel):
  id: UUID4
  host_id: UUID4
  config: Any
  metadata: dict[str, Any]
  error: Optional[str]
  running: bool
  

class TASK_CONSTANTS:
  # fetch descriptors
  FD_REGISTER_TASK_HOST = "register_task_host"
  FD_LIST_TASK_HOSTS = "list_task_hosts"
  
  FD_TM_TASK_START = "start_task"
  FD_TM_TASK_CANCEL = "cancel_task"
  
  FD_TASK_START = "start"
  FD_TASK_CANCEL = "cancel"
  
  # ports
  PORT_TASK_STATUS_REPORT_SERVER = 1000

class TaskHost(Worker):
  def __init__(self, node_link: Link, switch: Switch | None = None):
    super().__init__(node_link, switch)
    self.client: Client
    self.tasks: dict[str, asyncio.Task] = {}
  
  @property
  def metadata(self): return {}

  # TODO: deregister
  async def register(self, address: int):
    if not hasattr(self, "client"): raise ValueError("Client not created yet!")
    if self.client.address is None: raise ValueError("Client had no address!")
    registration = TaskHostRegistration(id=uuid4(), address=self.client.address, metadata=self.metadata)
    await self.client.fetch(address, TASK_CONSTANTS.FD_REGISTER_TASK_HOST, registration.model_dump())
  
  async def start(self):
    try:
      await self.setup()
      self.client = await self.create_client()
      await self.client.request_address()
      await asyncio.gather(self.start_receiver())
    finally:
      for task in self.tasks.values(): task.cancel()
      await asyncio.wait(self.tasks.values(), 1) # NOTE: make configurable
      await self.shutdown()
    
  @abstractmethod
  async def create_task(self, config: Any) -> Task: pass
  async def run_task(self, id: str, task: Task, report_address: int):
    error_text = None
    try:
      await task.run()
    except BaseException as e:
      error_text = str(e)
    await self.client.send_to((report_address, TASK_CONSTANTS.PORT_TASK_STATUS_REPORT_SERVER), MessagePackData(TaskShutdownReport(id=id, error=error_text).model_dump()))
    self.tasks.pop(id, None)
    
  async def start_receiver(self):
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
      
    await fetch_server.start()


class TaskManager(Worker):
  def __init__(self, node_link: Link, switch: Switch | None = None):
    super().__init__(node_link, switch)
    self.client: Client
    self.task_hosts: dict[UUID4, TaskHostRegistration] = {}
    self.tasks: dict[UUID4, TaskInstance] = {}
  
  async def start(self):
    try:
      await self.setup()
      self.client = await self.create_client()
      await self.client.request_address()
      await asyncio.gather(self.start_fetch_server(), self.start_report_server())
    finally: 
      await self.shutdown()
  
  async def start_report_server(self):
    async with AddressReceiver(self.client, self.client.address, TASK_CONSTANTS.PORT_TASK_STATUS_REPORT_SERVER) as receiver:
      while True:
        try:
          message: SerializableData = (await receiver.recv())[1]
          report = TaskShutdownReport.model_validate(message.data)
          
          task = self.tasks[report.id]
          task.running = False
          task.error = report.error
          
          # TODO: boadcast shutdown
        except asyncio.CancelledError: break
        except BaseException as e: logging.debug(e)
  
  async def start_fetch_server(self):
    fetch_server = FetchServer(self.client)
    
    @fetch_server.route(TASK_CONSTANTS.FD_REGISTER_TASK_HOST)
    async def _(req: FetchRequest):
      try:
        reg = TaskHostRegistration.model_validate(req.body)
        self.task_hosts[reg.id] = reg
        await req.respond("OK")
      except (ValidationError, KeyError) as e: await req.respond_error(new_fetch_body_bad_request(str(e)))
      
    @fetch_server.route(TASK_CONSTANTS.FD_LIST_TASK_HOSTS) 
    async def _(req: FetchRequest): await req.respond(TaskHostRegistrationList.dump_python(list(self.task_hosts.values())))
      
    @fetch_server.route(TASK_CONSTANTS.FD_TM_TASK_START)
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
          running=True
        )
        self.tasks[inst.id] = inst
        
        task_start_result = await self.client.fetch(task_host.address, TASK_CONSTANTS.FD_TASK_START, th_req.model_dump())
        task_start_result: TaskStartResponse = TaskStartResponse.model_validate(task_start_result)
        
        inst.metadata=task_start_result.metadata,
        inst.error=task_start_result.error,
        inst.running=task_start_result.error is None
        
        await req.respond(inst.model_dump())
      except (ValidationError, KeyError) as e: await req.respond_error(new_fetch_body_bad_request(str(e)))
      except BaseException as e: await req.respond_error(new_fetch_body_general_error(str(e)))
    
    @fetch_server.route(TASK_CONSTANTS.FD_TM_TASK_CANCEL)
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

    await fetch_server.start()