from typing import Any, Optional

from pydantic import BaseModel
from streamtasks.asgi import asgi_app_not_found
from abc import ABC, abstractmethod
from streamtasks.client import Client
import asyncio

from streamtasks.client.fetch import FetchRequest, FetchServer
from streamtasks.net import Link, Switch
from streamtasks.net.message.data import MessagePackData
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
  report_server: tuple[int, int]
  config: Any

class TaskStartResponse(BaseModel):
  id: str
  error: Optional[str]
  metadata: dict[str, Any]
  
class TaskShutdownReport(BaseModel):
  id: str
  error: Optional[str]

class TaskHost(Worker):
  def __init__(self, node_link: Link, switch: Switch | None = None):
    super().__init__(node_link, switch)
    self.client: Client
    self.tasks: dict[str, asyncio.Task] = {}
  
  async def start(self):
    try:
      await self.setup()
      self.client = await self.create_client()
      await asyncio.gather(self.start_receiver())
    finally:
      for task in self.tasks.values(): task.cancel()
      await asyncio.wait(self.tasks.values(), 1) # NOTE: make configurable
      await self.shutdown()
    
  @abstractmethod
  async def create_task(self, config: Any) -> Task: pass
  async def run_task(self, id: str, task: Task, report_server: tuple[int, int]):
    error_text = None
    try:
      await task.run()
    except BaseException as e:
      error_text = str(e)
    await self.client.send_to(report_server, MessagePackData(TaskShutdownReport(id=id, error=error_text).model_dump()))
    self.tasks.pop(id, None)
    
  async def start_receiver(self):
    fetch_server = FetchServer(self.client)
    
    @fetch_server.route("start")
    async def _(req: FetchRequest):
      body = TaskStartRequest.model_validate(req.body)
      try:
        task = await self.create_task(body.config)
        metadata = await asyncio.wait_for(task.setup(), 1) # NOTE: make this configurable
        self.tasks[body.id] = asyncio.create_task(self.run_task(body.id, task, body.report_server))
        await req.respond(TaskStartResponse(
          id=body.id,
          metadata=metadata,
          error=None
        ))
      except BaseException as e:
        await req.respond(TaskStartResponse(id=body.id, error=str(e), metadata={}))
      
    await fetch_server.start()