from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel
from streamtasks.net.message.data import MessagePackData
from streamtasks.system.configurators import static_configurator
from streamtasks.utils import get_timestamp_ms
from streamtasks.net.message.structures import IdMessage, TimestampMessage
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
import asyncio

class PulseGeneratorConfig(BaseModel):
  interval: float
  message_type: Literal["id", "ts"]
  out_topic: int
  
class TimePulseGeneratorConfig(PulseGeneratorConfig):
  message_type: Literal["ts"] = "ts"

class IdPulseGeneratorConfig(PulseGeneratorConfig):
  message_type: Literal["id"] = "id"

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
          await self.out_topic.send(MessagePackData(IdMessage(id=str(uuid4())).model_dump()))
        elif self.message_type == "ts":
          await self.out_topic.send(MessagePackData(TimestampMessage(timestamp=get_timestamp_ms()).model_dump()))
        await asyncio.sleep(self.interval)

class TimePulseGeneratorTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="time pulse generator",
    description="generates a time pulse in a specified interval.",
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic" }],
    default_config={ "interval": 1 },
    editor_fields=[{
        "type": "number",
        "key": "interval",
        "label": "interval",
        "min": 0,
        "integer": False,
        "unit": "s"
    }]
  )}
  async def create_task(self, config: Any, topic_space_id: int | None):
    return PulseGeneratorTask(await self.create_client(topic_space_id), TimePulseGeneratorConfig.model_validate(config))

class IdPulseGeneratorTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="id pulse generator",
    description="generates an id pulse in a specified interval.",
    outputs=[{ "label": "output", "type": "id", "key": "out_topic" }],
    default_config={ "interval": 1 },
    editor_fields=[{
        "type": "number",
        "key": "interval",
        "label": "interval",
        "min": 0,
        "integer": False,
        "unit": "s"
    }]
  )}
  async def create_task(self, config: Any, topic_space_id: int | None):
    return PulseGeneratorTask(await self.create_client(topic_space_id), IdPulseGeneratorConfig.model_validate(config))