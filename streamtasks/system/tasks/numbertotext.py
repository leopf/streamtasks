from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.message.types import NumberMessage, TextMessage
from streamtasks.net.serialization import RawData
from streamtasks.net.messages import TopicControlData
from streamtasks.system.configurators import static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class NumberToTextConfigBase(BaseModel):
  pass

class NumberToTextConfig(NumberToTextConfigBase):
  out_topic: int
  in_topic: int

class NumberToTextTask(Task):
  def __init__(self, client: Client, config: NumberToTextConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config

  async def run(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      while True:
        try:
          data = await self.in_topic.recv_data_control()
          if isinstance(data, TopicControlData): await self.out_topic.set_paused(data.paused)
          else:
            message = NumberMessage.model_validate(data.data)
            await self.out_topic.send(RawData(TextMessage(timestamp=message.timestamp, value=str(message.value)).model_dump()))
        except ValidationError: pass

class NumberToTextTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="Number To Text",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "content": "number" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "text" }],
    default_config=NumberToTextConfigBase().model_dump(),
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return NumberToTextTask(await self.create_client(topic_space_id), NumberToTextConfig.model_validate(config))
