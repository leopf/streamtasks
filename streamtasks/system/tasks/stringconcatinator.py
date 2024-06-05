
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.client.topic import PrioritizedSequentialInTopicSynchronizer
from streamtasks.net.serialization import RawData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.message.types import NumberMessage, TextMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
import asyncio

class StringConcatinatorConfigBase(BaseModel):
  synchronized: bool = True

class StringConcatinatorConfig(StringConcatinatorConfigBase):
  control_topic: int
  in_topic: int
  out_topic: int

class StringConcatinatorTask(Task):
  def __init__(self, client: Client, config: StringConcatinatorConfig):
    super().__init__(client)
    if config.synchronized:
      sync = PrioritizedSequentialInTopicSynchronizer()
      # make sure data arrives before trigger (if timestamps match)
      sync.set_priority(config.in_topic, 1)
      sync.set_priority(config.control_topic, 0)
      self.in_topic = self.client.sync_in_topic(config.in_topic, sync)
      self.control_topic = self.client.sync_in_topic(config.control_topic, sync)
    else:
      self.in_topic = self.client.in_topic(config.in_topic)
      self.control_topic = self.client.in_topic(config.control_topic)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.value = ""

  async def run(self):
    async with self.in_topic, self.control_topic, self.out_topic, self.in_topic.RegisterContext(), \
            self.control_topic.RegisterContext(), self.out_topic.RegisterContext():
      self.client.start()
      await asyncio.gather(self.run_control_recv(), self.run_receiver())

  async def run_control_recv(self):
    last_control = 0
    while True:
      try:
        data = await self.control_topic.recv_data_control()
        if isinstance(data, TopicControlData): await self.out_topic.set_paused(data.paused)
        else:
          message = NumberMessage.model_validate(data.data)
          if last_control <= 0.5 and message.value > 0.5 and len(self.value) > 0:
            await self.out_topic.send(RawData(TextMessage(timestamp=message.timestamp, value=self.value).model_dump()))
            self.value = ""
          last_control = message.value
      except ValidationError: pass

  async def run_receiver(self):
    while True:
      try:
        data = await self.in_topic.recv_data()
        message = TextMessage.model_validate(data.data)
        self.value += message.value
      except ValidationError: pass

class StringConcatinatorTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="String Concatinator",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "content": "text" }, { "label": "control", "type": "ts", "content": "number", "key": "control_topic" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "text" }],
    default_config=StringConcatinatorConfigBase().model_dump(),
    editor_fields=[EditorFields.boolean(key="synchronized")]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return StringConcatinatorTask(await self.create_client(topic_space_id), StringConcatinatorConfig.model_validate(config))
