from contextlib import AsyncExitStack
from typing import Any
from pydantic import BaseModel
from streamtasks.net.serialization import RawData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.tasks.ui.controlbase import UIControlBaseTask, UIControlBaseTaskConfig
from streamtasks.utils import get_timestamp_ms
from streamtasks.message.types import NumberMessage
from streamtasks.system.task import TaskHost
from streamtasks.client import Client

class SliderUIConfigBase(UIControlBaseTaskConfig):
  label: str = "slider"
  default_value: float = 0
  min_value: float = 0
  max_value: float = 1

class SliderUIConfig(SliderUIConfigBase):
  out_topic: int

class SliderValue(BaseModel):
  value: float

class SliderUITask(UIControlBaseTask[SliderUIConfig, SliderValue]):
  def __init__(self, client: Client, config: SliderUIConfig):
    super().__init__(client, config, SliderValue(value=config.default_value), "slider.js")
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config

  async def context(self):
    exit_stack = AsyncExitStack()
    await exit_stack.enter_async_context(self.out_topic)
    await exit_stack.enter_async_context(self.out_topic.RegisterContext())
    return exit_stack

  async def send_value(self, value: SliderValue):
    await self.out_topic.send(RawData(NumberMessage(timestamp=get_timestamp_ms(), value=value.value).model_dump()))

class SliderUITaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="Slider UI",
    outputs=[{ "label": "output", "key": "out_topic", "type": "ts", "content": "number" }],
    default_config=SliderUIConfigBase().model_dump(),
    config_to_output_map=[{ "label": "label" }],
    editor_fields=[
      EditorFields.text(key="label"),
      EditorFields.number(key="default_value"),
      EditorFields.number(key="min_value"),
      EditorFields.number(key="max_value"),
      EditorFields.repeat_interval()
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return SliderUITask(await self.create_client(topic_space_id), SliderUIConfig.model_validate(config))
