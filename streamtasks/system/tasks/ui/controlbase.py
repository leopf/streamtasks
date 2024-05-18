from abc import abstractmethod
import asyncio
import importlib.resources
from typing import Any, AsyncContextManager, Generic, TypeVar
from pydantic import BaseModel
from streamtasks.asgi import ASGIAppRunner
from streamtasks.asgiserver import ASGIRouter, ASGIServer, HTTPContext, WebsocketContext, http_context_handler, websocket_context_handler
from streamtasks.client import Client
from streamtasks.net.utils import endpoint_to_str
from streamtasks.services.protocols import WorkerPorts
from streamtasks.system.task import MetadataFields, Task
from streamtasks.utils import AsyncTrigger, wait_with_dependencies

C = TypeVar("C", bound=BaseModel)
V = TypeVar("V", bound=BaseModel)

class UIBaseTask(Task, Generic[C, V]):
  def __init__(self, client: Client, config: C, default_value: V, script_name: str):
    super().__init__(client)
    self.config: C = config
    self.value: V = default_value
    self.script_name = script_name
    self.value_changed_trigger = AsyncTrigger()

  @abstractmethod
  async def context(self) -> AsyncContextManager: pass

  @abstractmethod
  async def run_other(self) -> AsyncContextManager: pass

  async def setup(self) -> dict[str, Any]:
    self.client.start()
    await self.client.request_address()
    return {
      MetadataFields.ASGISERVER: endpoint_to_str((self.client.address, WorkerPorts.ASGI)),
      "cfg:frontendpath": "index.html",
      **(await super().setup())
    }

  async def run(self):
    async with await self.context():
      await asyncio.gather(self.run_other(), self._run_web_server())

  async def _run_web_server(self):
    app = ASGIServer()
    router = ASGIRouter()
    app.add_handler(router)

    @router.get("/index.html")
    @http_context_handler
    async def _(ctx: HTTPContext):
      with open(importlib.resources.files(__name__).joinpath("resources/controlbase.html")) as fd:
        await ctx.respond_text(fd.read(), mime_type="text/html")

    @router.get("/main.js")
    @http_context_handler
    async def _(ctx: HTTPContext):
      with open(importlib.resources.files(__name__).joinpath("resources/" + self.script_name)) as fd:
        await ctx.respond_text(fd.read(), mime_type="application/javascript")

    @router.get("/value")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json(self.value.model_dump())

    @router.get("/config")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json(self.config.model_dump())

    @router.post("/value")
    @http_context_handler
    async def _(ctx: HTTPContext):
      self.value = self.value.__class__.model_validate(await ctx.receive_json())
      self.value_changed_trigger.trigger()
      await ctx.respond_status(200)

    @router.websocket_route("/value")
    @websocket_context_handler
    async def _(ctx: WebsocketContext):
      try:
        await ctx.accept()
        receive_disconnect_task = asyncio.create_task(ctx.receive_disconnect())
        while ctx.connected:
          await wait_with_dependencies(self.value_changed_trigger.wait(), [receive_disconnect_task])
          if ctx.connected:
            await ctx.send_message(self.value.model_dump_json())
      finally:
        receive_disconnect_task.cancel()
        await ctx.close()

    await ASGIAppRunner(self.client, app).run()

class UIControlBaseTaskConfig(BaseModel):
  repeat_interval: float = 1

C2 = TypeVar("C2", bound=UIControlBaseTaskConfig)

class UIControlBaseTask(UIBaseTask[C2, V]):
  def __init__(self, client: Client, config: C2, default_value: V, script_name: str):
    super().__init__(client, config, default_value, script_name)

  @abstractmethod
  async def send_value(self, value: V): pass

  async def run_other(self) -> AsyncContextManager:
    while True:
      await self.send_value(self.value)
      try: await asyncio.wait_for(self.value_changed_trigger.wait(), self.config.repeat_interval)
      except asyncio.TimeoutError: pass
