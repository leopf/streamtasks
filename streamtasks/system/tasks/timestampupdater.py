from typing import Any, Literal
from pydantic import BaseModel
from streamtasks.net.message.types import TopicControlData
from streamtasks.net.message.utils import get_timestamp_from_message, set_timestamp_on_message
from streamtasks.system.configurators import static_configurator
from streamtasks.utils import get_timestamp_ms
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class TimestampUpdaterConfig(BaseModel):
  out_topic: int
  in_topic: int
  time_reference: Literal["message", "time"] = "time"
  time_offset: int = 0
  fail_closed: bool = True

class TimestampUpdaterTask(Task):
  def __init__(self, client: Client, config: TimestampUpdaterConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.reference: Literal["message", "time"] = config.time_reference
    self.offset = config.time_offset 
    self.fail_closed = config.fail_closed

  async def run(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      while True:
        data = await self.in_topic.recv_data_control()
        if isinstance(data, TopicControlData):
          await self.out_topic.set_paused(data.paused)
        else:
          try:
            if self.reference == "message": ref_time = get_timestamp_from_message(data)
            else: ref_time = get_timestamp_ms()
            data = data.copy()
            set_timestamp_on_message(data, ref_time + self.offset)
            await self.out_topic.send(data)
          except:
            if not self.fail_closed: await self.out_topic.send(data)

class TimestampUpdaterTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="pulse generator",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic" }],
    default_config={ "time_reference": "time", "time_offset": 0, "fail_closed": True }
  )}
  async def create_task(self, config: Any):
    return TimestampUpdaterTask(await self.create_client(), TimestampUpdaterConfig.model_validate(config))
  