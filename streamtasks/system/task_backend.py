

import asyncio
from fastapi import FastAPI
from pydantic import UUID4
from streamtasks.asgi import ASGIAppRunner
from streamtasks.client import Client
from streamtasks.net import Link, Switch
from streamtasks.services.protocols import AddressNames
from streamtasks.system.task import TMTaskStartRequest, TaskManagerClient
from streamtasks.worker import Worker


class ASGITaskManagementBackend(Worker):
  def __init__(self, node_link: Link, switch: Switch | None = None, task_manager_address_name: str = AddressNames.TASK_MANAGER):
    super().__init__(node_link, switch)
    self.task_manager_address_name = task_manager_address_name
    self.client: Client
    self.tm_client: TaskManagerClient
  
  async def run(self):
    try:
      await self.setup()
      self.client = await self.create_client()
      self.client.start()
      await self.client.request_address()
      # TODO: register a name?
      self.tm_client = TaskManagerClient(self.client, self.task_manager_address_name)
      await asyncio.gather(self.run_asgi_server())
    finally:
      await self.shutdown()
      
  async def run_asgi_server(self):
    app = FastAPI()
    @app.get("/api/task-hosts")
    async def _(): return await self.tm_client.list_task_hosts()
    
    @app.post("/api/task/start")
    async def _(req: TMTaskStartRequest): return await self.tm_client.start_task(req.task_host_id, req.config) # TODO: there is a better way!
    
    @app.post("/api/task/stop/{id}")
    async def _(id: UUID4): return await self.tm_client.cancel_task_wait(id)
    
    @app.post("/api/task/cancel/{id}")
    async def _(id: UUID4): await self.tm_client.cancel_task(id)
    
    
    runner = ASGIAppRunner(self.client, app)
    await runner.run()