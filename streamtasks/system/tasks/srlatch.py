import asyncio
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.client.topic import InTopic, SequentialInTopicSynchronizer
from streamtasks.net.serialization import RawData
from streamtasks.message.types import NumberMessage
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class SRLatchConfigBase(BaseModel):
  default_value: bool = False
  synchronized: bool = True

class SRLatchConfig(SRLatchConfigBase):
  out_topic: int
  set_topic: int
  reset_topic: int

class SRLatchTask(Task):
  def __init__(self, client: Client, config: SRLatchConfig):
    super().__init__(client)
    if config.synchronized:
      sync = SequentialInTopicSynchronizer()
      self.set_topic = self.client.sync_in_topic(config.set_topic, sync)
      self.reset_topic = self.client.sync_in_topic(config.reset_topic, sync)
    else:
      self.set_topic = self.client.in_topic(config.set_topic)
      self.reset_topic = self.client.in_topic(config.reset_topic)

    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.set_value = False
    self.reset_value = False
    self.value = config.default_value

  async def run(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.set_topic, self.set_topic.RegisterContext(), self.reset_topic, self.reset_topic.RegisterContext():
      self.client.start()
      await asyncio.gather(self._run_receive(self.set_topic, "set_value"), self._run_receive(self.reset_topic, "reset_value"))

  async def _run_receive(self, topic: InTopic, value_name: str):
    while True:
      try:
        data = await topic.recv_data()
        message = NumberMessage.model_validate(data.data)
        setattr(self, value_name, message.value > 0.5)
        await self.send(message.timestamp)
      except ValidationError: pass

  async def send(self, timestamp: int):
    if self.set_value != self.reset_value:
      if self.set_value: self.value = True
      if self.reset_value: self.value = False
    await self.out_topic.send(RawData(NumberMessage(timestamp=timestamp, value=self.value).model_dump()))

class SRLatchTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="SR Latch",
    inputs=[{ "label": "set", "type": "ts", "key": "set_topic", "content": "number" }, { "label": "reset", "type": "ts", "key": "reset_topic", "content": "number" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "number" }],
    default_config=SRLatchConfigBase().model_dump(),
    editor_fields=[
      EditorFields.boolean("default_value"),
      EditorFields.boolean("synchronized"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return SRLatchTask(await self.create_client(topic_space_id), SRLatchConfig.model_validate(config))
