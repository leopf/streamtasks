from contextlib import AsyncExitStack
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.system.configurators import DEFAULT_COLORS, EditorFields, static_configurator
from streamtasks.system.tasks.ui.controlbase import UIBaseTask, UIControlBaseTaskConfig
from streamtasks.message.types import NumberMessage
from streamtasks.system.task import TaskHost
from streamtasks.client import Client

class StatusDisplayConfigBase(UIControlBaseTaskConfig):
  text_above: str = "good"
  color_above: str = DEFAULT_COLORS[4][0]
  text_below: str = "bad"
  color_below: str = DEFAULT_COLORS[17][0]
  threshold: float = 0.5

class StatusDisplayConfig(StatusDisplayConfigBase):
  in_topic: int

class StatusDisplayValue(BaseModel):
  value: float

class StatusDisplayTask(UIBaseTask[StatusDisplayConfig, StatusDisplayValue]):
  def __init__(self, client: Client, config: StatusDisplayConfig):
    super().__init__(client, config, StatusDisplayValue(value=config.threshold), "status-display.js")
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
        message = NumberMessage.model_validate(data.data)
        self.value = StatusDisplayValue(value=message.value)
      except ValidationError: pass

class StatusDisplayTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="Status Display",
    inputs=[{ "label": "value", "key": "in_topic", "type": "ts", "content": "number" }],
    default_config=StatusDisplayConfigBase().model_dump(),
    editor_fields=[
      EditorFields.text(key="text_above"),
      EditorFields.color_select(key="color_above"),
      EditorFields.text(key="text_below"),
      EditorFields.color_select(key="color_below"),
      EditorFields.number(key="threshold"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return StatusDisplayTask(await self.create_client(topic_space_id), StatusDisplayConfig.model_validate(config))
