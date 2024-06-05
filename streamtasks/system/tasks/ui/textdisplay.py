from contextlib import AsyncExitStack
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.tasks.ui.controlbase import UIBaseTask, UIControlBaseTaskConfig
from streamtasks.message.types import TextMessage
from streamtasks.system.task import TaskHost
from streamtasks.client import Client

class TextDisplayConfigBase(UIControlBaseTaskConfig):
  max_length: int = 2000
  seperator: str = ""
  append: bool = True

class TextDisplayConfig(TextDisplayConfigBase):
  in_topic: int

class TextDisplayValue(BaseModel):
  value: str

class TextDisplayTask(UIBaseTask[TextDisplayConfig, TextDisplayValue]):
  def __init__(self, client: Client, config: TextDisplayConfig):
    super().__init__(client, config, TextDisplayValue(value=""), "text-display.js")
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config

  async def context(self):
    exit_stack = AsyncExitStack()
    await exit_stack.enter_async_context(self.in_topic)
    await exit_stack.enter_async_context(self.in_topic.RegisterContext())
    return exit_stack

  async def run_other(self):
    while True:
      try:
        data = await self.in_topic.recv_data()
        message = TextMessage.model_validate(data.data)
        if self.config.append: new_text = self.value.value + self.config.seperator + message.value
        else: new_text = message.value
        if self.config.max_length != -1: new_text = new_text[-self.config.max_length:]
        self.value = TextDisplayValue(value=new_text)
      except ValidationError: pass

class TextDisplayTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="Text Display",
    inputs=[{ "label": "value", "key": "in_topic", "type": "ts", "content": "text" }],
    default_config=TextDisplayConfigBase().model_dump(),
    editor_fields=[
      EditorFields.integer(key="max_length", label="max text length (-1 for unlimited)", min_value=-1, unit="chars"),
      EditorFields.boolean(key="append", label="append incoming messages"),
      EditorFields.text(key="seperator"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return TextDisplayTask(await self.create_client(topic_space_id), TextDisplayConfig.model_validate(config))
