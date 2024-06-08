from contextlib import AsyncExitStack
from typing import Any
from pydantic import BaseModel
from streamtasks.net.serialization import RawData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.tasks.ui.controlbase import UIControlBaseTask, UIControlBaseTaskConfig
from streamtasks.utils import get_timestamp_ms
from streamtasks.message.types import TextMessage
from streamtasks.system.task import TaskHost
from streamtasks.client import Client

class TextInputConfigBase(UIControlBaseTaskConfig):
  repeat_interval: float = 0

class TextInputConfig(TextInputConfigBase):
  out_topic: int

class TextInputValue(BaseModel):
  value: str

class TextInputTask(UIControlBaseTask[TextInputConfig, TextInputValue]):
  def __init__(self, client: Client, config: TextInputConfig):
    super().__init__(client, config, TextInputValue(value=""), "text-input.js")
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config

  async def context(self):
    exit_stack = AsyncExitStack()
    await exit_stack.enter_async_context(self.out_topic)
    await exit_stack.enter_async_context(self.out_topic.RegisterContext())
    return exit_stack

  async def send_value(self, value: TextInputValue):
    if len(value.value.strip()) > 0:
      await self.out_topic.send(RawData(TextMessage(timestamp=get_timestamp_ms(), value=value.value).model_dump()))

class TextInputTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="Text Input",
    outputs=[{ "label": "output", "key": "out_topic", "type": "ts", "content": "text" }],
    default_config=TextInputConfigBase().model_dump(),
    editor_fields=[
      EditorFields.repeat_interval(min_value=0)
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return TextInputTask(await self.create_client(topic_space_id), TextInputConfig.model_validate(config))
