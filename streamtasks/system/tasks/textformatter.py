import asyncio
import contextlib
from streamtasks.client import Client
from streamtasks.client.topic import InTopic, SequentialInTopicSynchronizer
from streamtasks.system.configurators import EditorFields, multitrackio_configurator, static_configurator
from streamtasks.net.serialization import RawData
from streamtasks.message.types import TextMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.task import Task, TaskHost
from pydantic import BaseModel, ValidationError
from typing import Any

class TextFormatterVariableConfigBase(BaseModel):
  name: str = "a"
  default_text: str = ""

class TextFormatterVariableConfig(TextFormatterVariableConfigBase):
  in_topic: int

class TextFormatterConfigBase(BaseModel):
  variable_tracks: list[TextFormatterVariableConfig] = []
  template: str = ""
  synchronized: bool = True

class TextFormatterConfig(TextFormatterConfigBase):
  out_topic: int

class TextFormatterTask(Task):
  def __init__(self, client: Client, config: TextFormatterConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.var_values = { input_var.name: input_var.default_text for input_var in config.variable_tracks }

    if config.synchronized:
      sync = SequentialInTopicSynchronizer()
      self.in_topics = [
        (client.sync_in_topic(input_var.in_topic, sync), input_var.name, input_var.default_text)
        for input_var in config.variable_tracks
      ]
    else:
      self.in_topics = [
        (client.in_topic(input_var.in_topic), input_var.name, input_var.default_text)
        for input_var in config.variable_tracks
      ]

  async def run(self):
    tasks: list[asyncio.Task] = []
    try:
      async with contextlib.AsyncExitStack() as exit_stack:
        await exit_stack.enter_async_context(self.out_topic)
        await exit_stack.enter_async_context(self.out_topic.RegisterContext())
        for in_topic, var_name, default_value in self.in_topics:
          await exit_stack.enter_async_context(in_topic)
          await exit_stack.enter_async_context(in_topic.RegisterContext())
          tasks.append(asyncio.create_task(self.run_input(in_topic, var_name, default_value)))
        self.client.start()
        await asyncio.gather(*tasks)
    finally:
      for task in tasks: task.cancel()

  async def run_input(self, in_topic: InTopic, var_name: str, default_text: str):
    while True:
      data = await in_topic.recv_data_control()
      if isinstance(data, TopicControlData): self.var_values[var_name] = default_text
      else:
        try:
          message = TextMessage.model_validate(data.data)
          self.var_values[var_name] = message.value
          await self.send_value(message.timestamp)
        except ValidationError: pass

  async def send_value(self, timestamp: int):
    result = self.config.template.format_map(self.var_values)
    await self.out_topic.send(RawData(TextMessage(timestamp=timestamp,value=result).model_dump()))

class TextFormatterTaskHost(TaskHost):
  @property
  def metadata(self): return {
    **static_configurator(
      label="text formatter",
      default_config=TextFormatterConfigBase().model_dump(),
      outputs=[{ "label": "output", "type": "ts", "content": "text", "key": "out_topic" }],
      editor_fields=[
        EditorFields.text(key="template"),
        EditorFields.boolean("synchronized"),
    ]),
    **multitrackio_configurator(is_input=True, track_configs=[
      {
        "key": "variable",
        "multiLabel": "variables",
        "defaultConfig": TextFormatterVariableConfigBase().model_dump(),
        "defaultIO": { "type": "ts", "content": "text" },
        "ioMap": { "name": "label" },
        "editorFields": [
          EditorFields.text(key="name"),
          EditorFields.text(key="default_text"),
        ]
      }
    ])
  }
  async def create_task(self, config: Any, topic_space_id: int | None):
    return TextFormatterTask(await self.create_client(topic_space_id), TextFormatterConfig.model_validate(config))
