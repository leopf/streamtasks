from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel
from streamtasks.net.serialization import RawData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.utils import get_timestamp_ms
from streamtasks.message.types import IdMessage, TimestampMessage
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
import asyncio

class PulseGeneratorConfigBase(BaseModel):
  interval: float = 1
  message_type: Literal["id", "ts"] = "ts"

class PulseGeneratorConfig(PulseGeneratorConfigBase):
  out_topic: int

class PulseGeneratorTask(Task):
  def __init__(self, client: Client, config: PulseGeneratorConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.interval = config.interval
    self.message_type: Literal["id", "ts"] = config.message_type

  async def run(self):
    async with self.out_topic, self.out_topic.RegisterContext():
      self.client.start()
      while True:
        if self.message_type == "id":
          await self.out_topic.send(RawData(IdMessage(id=str(uuid4())).model_dump()))
        elif self.message_type == "ts":
          await self.out_topic.send(RawData(TimestampMessage(timestamp=get_timestamp_ms()).model_dump()))
        await asyncio.sleep(self.interval)

class PulseGeneratorTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="pulse generator",
    description="generates a pulse in a specified interval.",
    outputs=[{ "label": "output", "key": "out_topic" }],
    default_config=PulseGeneratorConfigBase().model_dump(),
    config_to_output_map=[{ "message_type": "type" }],
    editor_fields=[
      EditorFields.select(key="message_type", items=[("ts", "Timestamp"), ("id", "Id")]),
      EditorFields.number(key="interval", min_value=0.001, unit="s")
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return PulseGeneratorTask(await self.create_client(topic_space_id), PulseGeneratorConfig.model_validate(config))
