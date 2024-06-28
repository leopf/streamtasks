from datetime import datetime
from typing import Any
from pydantic import BaseModel
from streamtasks.message.types import TextMessage
from streamtasks.net.serialization import RawData
from streamtasks.net.messages import TopicControlData
from streamtasks.message.utils import get_timestamp_from_message
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class TimeToTextConfigBase(BaseModel):
  date_format: str = "%d/%m/%Y, %H:%M:%S"

class TimeToTextConfig(TimeToTextConfigBase):
  out_topic: int
  in_topic: int

class TimeToTextTask(Task):
  def __init__(self, client: Client, config: TimeToTextConfig):
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
            timestamp = get_timestamp_from_message(data)
            value = datetime.fromtimestamp(timestamp / 1000).strftime(self.config.date_format)
            await self.out_topic.send(RawData(TextMessage(timestamp=timestamp, value=value).model_dump()))
        except ValueError: pass

class TimeToTextTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="Time To Text",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "text" }],
    default_config=TimeToTextConfigBase().model_dump(),
    free_inputs=["in_topic"],
    editor_fields=[
      EditorFields.text("date_format")
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return TimeToTextTask(await self.create_client(topic_space_id), TimeToTextConfig.model_validate(config))
