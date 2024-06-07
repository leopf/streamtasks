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

class SwitchUIConfigBase(UIControlBaseTaskConfig):
  label: str = "switch"
  default_value: bool = False

class SwitchUIConfig(SwitchUIConfigBase):
  out_topic: int

class SwitchValue(BaseModel):
  value: bool

class SwitchUITask(UIControlBaseTask[SwitchUIConfig, SwitchValue]):
  def __init__(self, client: Client, config: SwitchUIConfig):
    super().__init__(client, config, SwitchValue(value=config.default_value), "switch.js")
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config

  async def context(self):
    exit_stack = AsyncExitStack()
    await exit_stack.enter_async_context(self.out_topic)
    await exit_stack.enter_async_context(self.out_topic.RegisterContext())
    return exit_stack

  async def send_value(self, value: SwitchValue):
    await self.out_topic.send(RawData(NumberMessage(timestamp=get_timestamp_ms(), value=1 if value.value else 0).model_dump()))

class SwitchUITaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="Switch UI",
    outputs=[{ "label": "output", "key": "out_topic", "type": "ts", "content": "number" }],
    default_config=SwitchUIConfigBase().model_dump(),
    config_to_output_map=[{ "label": "label" }],
    editor_fields=[
      EditorFields.text(key="label"),
      EditorFields.boolean(key="default_value", label="default on/off"),
      EditorFields.repeat_interval()
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return SwitchUITask(await self.create_client(topic_space_id), SwitchUIConfig.model_validate(config))
