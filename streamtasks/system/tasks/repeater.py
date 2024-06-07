import asyncio
from typing import Any
from pydantic import BaseModel
from streamtasks.net.serialization import RawData
from streamtasks.net.messages import TopicControlData
from streamtasks.message.utils import get_timestamp_from_message, set_timestamp_on_message
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.utils import TimeSynchronizer
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class RepeaterConfigBase(BaseModel):
  interval: int = 1000
  fail_closed: bool = False

class RepeaterConfig(RepeaterConfigBase):
  out_topic: int
  in_topic: int

class RepeaterTask(Task):
  def __init__(self, client: Client, config: RepeaterConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.interval = config.interval
    self.fail_closed = config.fail_closed
    self.current_message: RawData | None = None
    self.time_sync = TimeSynchronizer()

  async def run(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      await asyncio.gather(self._run_receiver(), self._run_sender())

  async def _run_receiver(self):
    while True:
      data = await self.in_topic.recv_data_control()
      if isinstance(data, TopicControlData):
        await self.out_topic.set_paused(data.paused)
      else:
        try:
          msg_time = get_timestamp_from_message(data)
          self.time_sync.update(msg_time)
          self.current_message = data.copy()
          await self.out_topic.send(data)
        except ValueError:
          if not self.fail_closed: await self.out_topic.send(data)
          else: self.current_message = None

  async def _run_sender(self):
    while True:
      await asyncio.sleep(self.interval / 1000)
      if not self.out_topic.is_paused and self.current_message is not None:
        try:
          msg = self.current_message.copy()
          set_timestamp_on_message(msg, self.time_sync.time)
          await self.out_topic.send(msg)
        except ValueError: pass

class RepeaterTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="repeater",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic" }],
    default_config=RepeaterConfigBase().model_dump(),
    io_mirror=[("in_topic", 0)],
    editor_fields=[
      EditorFields.integer(key="interval", min_value=1, unit="ms"),
      EditorFields.boolean(key="fail_closed"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return RepeaterTask(await self.create_client(topic_space_id), RepeaterConfig.model_validate(config))
