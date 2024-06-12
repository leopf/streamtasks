from typing import Any, Literal
from pydantic import BaseModel
from streamtasks.net.messages import TopicControlData
from streamtasks.message.utils import get_timestamp_from_message, set_timestamp_on_message
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.utils import get_timestamp_ms
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class TimestampUpdaterConfigBase(BaseModel):
  time_reference: Literal["message", "clock"] = "clock"
  time_offset: int = 0
  fail_closed: bool = True

class TimestampUpdaterConfig(TimestampUpdaterConfigBase):
  out_topic: int
  in_topic: int

class TimestampUpdaterTask(Task):
  def __init__(self, client: Client, config: TimestampUpdaterConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config

  async def run(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      while True:
        data = await self.in_topic.recv_data_control()
        if isinstance(data, TopicControlData):
          await self.out_topic.set_paused(data.paused)
        else:
          try:
            if self.config.time_reference == "message": ref_time = get_timestamp_from_message(data)
            else: ref_time = get_timestamp_ms()
            data = data.copy()
            set_timestamp_on_message(data, ref_time + self.config.time_offset)
            await self.out_topic.send(data)
          except (ValueError, KeyError):
            if not self.config.fail_closed: await self.out_topic.send(data)

class TimestampUpdaterTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="timestamp updater",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic" }],
    default_config=TimestampUpdaterConfigBase().model_dump(),
    io_mirror=[("in_topic", 0)],
    editor_fields=[
      EditorFields.select(key="time_reference", items=[("clock", "system time"), ("message", "message")]),
      EditorFields.integer(key="time_offset", label="time offset from reference", unit="ms"),
      EditorFields.boolean(key="fail_closed"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return TimestampUpdaterTask(await self.create_client(topic_space_id), TimestampUpdaterConfig.model_validate(config))
