from contextlib import AsyncExitStack
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.system.configurators import DEFAULT_COLORS, EditorFields, static_configurator
from streamtasks.system.tasks.ui.controlbase import UIBaseTask, UIControlBaseTaskConfig
from streamtasks.message.types import NumberMessage
from streamtasks.system.task import TaskHost
from streamtasks.client import Client

class ValueDisplayBarConfigBase(UIControlBaseTaskConfig):
  color: str = DEFAULT_COLORS[4][0]
  direction: str = "vertical"
  default_value: float = 0
  min_value: float = 0
  max_value: float = 1

class ValueDisplayBarConfig(ValueDisplayBarConfigBase):
  in_topic: int

class DisplayBarValue(BaseModel):
  value: float

class ValueDisplayBarTask(UIBaseTask[ValueDisplayBarConfig, DisplayBarValue]):
  def __init__(self, client: Client, config: ValueDisplayBarConfig):
    super().__init__(client, config, DisplayBarValue(value=config.default_value), "value-display-bar.js")
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
        self.value = DisplayBarValue(value=message.value)
      except ValidationError: pass

class ValueDisplayBarTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="Value Display Bar",
    inputs=[{ "label": "display value", "key": "in_topic", "type": "ts", "content": "number" }],
    default_config=ValueDisplayBarConfigBase().model_dump(),
    editor_fields=[
      EditorFields.color_select(key="color"),
      EditorFields.select(key="direction", items=[("vertical", "vertical"), ("horizontal", "horizontal")]),
      EditorFields.number(key="default_value"),
      EditorFields.number(key="min_value"),
      EditorFields.number(key="max_value"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return ValueDisplayBarTask(await self.create_client(topic_space_id), ValueDisplayBarConfig.model_validate(config))
