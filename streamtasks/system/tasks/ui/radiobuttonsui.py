import contextlib
from typing import Any
from pydantic import BaseModel
from streamtasks.net.serialization import RawData
from streamtasks.system.configurators import EditorFields, multitrackio_configurator, static_configurator
from streamtasks.system.tasks.ui.controlbase import UIControlBaseTask, UIControlBaseTaskConfig
from streamtasks.utils import get_timestamp_ms
from streamtasks.message.types import NumberMessage
from streamtasks.system.task import TaskHost
from streamtasks.client import Client

class RadioButtonConfigBase(BaseModel):
  label: str = "button"

class RadioButtonConfig(RadioButtonConfigBase):
  out_topic: int

class RadioButtonsUIConfig(UIControlBaseTaskConfig):
  button_tracks: list[RadioButtonConfig] = []

class RadioButtonsValue(BaseModel):
  selected_topic: int

class RadioButtonsUITask(UIControlBaseTask[RadioButtonsUIConfig, RadioButtonsValue]):
  def __init__(self, client: Client, config: RadioButtonsUIConfig):
    super().__init__(client, config, RadioButtonsValue(selected_topic=-1), "radiobuttons.js")
    self.out_topics = [ self.client.out_topic(t.out_topic) for t in config.button_tracks ]

  async def context(self):
    exit_stack = contextlib.AsyncExitStack()
    for out_topic in self.out_topics:
      await exit_stack.enter_async_context(out_topic)
      await exit_stack.enter_async_context(out_topic.RegisterContext())
    return exit_stack

  async def send_value(self, data: RadioButtonsValue):
    timestamp = get_timestamp_ms()
    for out_topic in self.out_topics:
      value = 1 if out_topic.topic == data.selected_topic else 0
      await out_topic.send(RawData(NumberMessage(timestamp=timestamp, value=value).model_dump()))

class RadioButtonsUITaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="Radio Buttons UI",
    default_config=RadioButtonsUIConfig().model_dump(),
    editor_fields=[
      EditorFields.repeat_interval()
    ]),
    **multitrackio_configurator(is_input=False, track_configs=[{
        "key": "button",
        "multiLabel": "buttons",
        "defaultConfig": RadioButtonConfigBase().model_dump(),
        "defaultIO": { "type": "ts", "content": "number" },
        "ioMap": { "label": "label" },
        "editorFields": [
          EditorFields.text(key="label")
        ]
    }])}

  async def create_task(self, config: Any, topic_space_id: int | None):
    return RadioButtonsUITask(await self.create_client(topic_space_id), RadioButtonsUIConfig.model_validate(config))
