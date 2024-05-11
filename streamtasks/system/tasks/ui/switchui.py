import os
import random
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel
from streamtasks.asgi import ASGIAppRunner
from streamtasks.asgiserver import ASGIRouter, ASGIServer, HTTPContext, WebsocketContext, http_context_handler, websocket_context_handler
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.utils import endpoint_to_str
from streamtasks.services.protocols import WorkerPorts
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.utils import AsyncTrigger, get_timestamp_ms, wait_with_dependencies
from streamtasks.net.message.structures import IdMessage, NumberMessage, TimestampMessage
from streamtasks.system.task import MetadataFields, Task, TaskHost
from streamtasks.client import Client
import asyncio

class SwitchUIConfigBase(BaseModel):
  label: str = "switch"
  repeat_interval: float = 1
  default_value: bool = False
  
class SwitchUIConfig(SwitchUIConfigBase):
  out_topic: int

class SetValueMessage(BaseModel):
  value: bool

class SwitchUITask(Task):
  def __init__(self, client: Client, config: SwitchUIConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.value = config.default_value
    self.value_changed_trigger = AsyncTrigger()

  async def setup(self) -> dict[str, Any]:
    self.client.start()
    await self.client.request_address()
    return {
      MetadataFields.ASGISERVER: endpoint_to_str((self.client.address, WorkerPorts.ASGI)),
      "cfg:frontendpath": "index.html",
      **(await super().setup())
    }

  async def run(self):
    async with self.out_topic, self.out_topic.RegisterContext():
      await asyncio.gather(self._run_sender(), self._run_updater(), self._run_web_server())
  
  async def _run_web_server(self):
    app = ASGIServer()
    router = ASGIRouter()
    app.add_handler(router)
    
    @router.get("/index.html")
    @http_context_handler
    async def _(ctx: HTTPContext):
      with open(os.path.join(os.path.dirname(__file__), "index.html")) as fd:
        await ctx.respond_text(fd.read(), mime_type="text/html")
      
    @router.get("/initial")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json({ "value": self.value, "label": self.config.label })
      
    @router.post("/value")
    @http_context_handler
    async def _(ctx: HTTPContext):
      data = SetValueMessage.model_validate(await ctx.receive_json())
      self.value = data.value
      self.value_changed_trigger.trigger()
      await ctx.respond_status(200)

    @router.get("/value")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json_string(SetValueMessage(value=self.value).model_dump_json())

    @router.websocket_route("/value")
    @websocket_context_handler
    async def _(ctx: WebsocketContext): 
      try:
        await ctx.accept()
        receive_disconnect_task = asyncio.create_task(ctx.receive_disconnect())
        while True:
          await wait_with_dependencies(self.value_changed_trigger.wait(), [receive_disconnect_task])
          if ctx.connected:
            await ctx.send_message(SetValueMessage(value=self.value).model_dump_json())
      finally:
        receive_disconnect_task.cancel()
        await ctx.close()

    runner = ASGIAppRunner(self.client, app)
    await runner.run()
  
  async def _run_updater(self):
    while True:
      await self.value_changed_trigger.wait()
      await self._send_value()
  
  async def _run_sender(self):
    while True:
      await self._send_value()
      await asyncio.sleep(self.config.repeat_interval)
  
  async def _send_value(self):
    await self.out_topic.send(MessagePackData(NumberMessage(timestamp=get_timestamp_ms(), value=1 if self.value else 0).model_dump()))

class SwitchUITaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="Switch UI",
    outputs=[{ "label": "output", "key": "out_topic", "type": "ts", "content": "number" }],
    default_config=SwitchUIConfigBase().model_dump(),
    editor_fields=[
      EditorFields.text(key="label"),
      EditorFields.boolean(key="default_value", label="default on/off"),
      EditorFields.number(key="repeat_interval", min_value=0.001, unit="s")
    ]
  )}
  async def create_task(self, config: Any, topic_space_id: int | None):
    return SwitchUITask(await self.create_client(topic_space_id), SwitchUIConfig.model_validate(config))
