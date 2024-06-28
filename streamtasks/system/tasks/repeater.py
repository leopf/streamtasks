import asyncio
import time
from typing import Any
from pydantic import BaseModel
from streamtasks.net.serialization import RawData
from streamtasks.net.messages import TopicControlData
from streamtasks.message.utils import get_timestamp_from_message, set_timestamp_on_message
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.utils import AsyncTrigger, TimeSynchronizer, hertz_to_fintervall
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class RepeaterConfigBase(BaseModel):
  rate: float | int = 10
  fail_closed: bool = False

class RepeaterConfig(RepeaterConfigBase):
  out_topic: int
  in_topic: int

class RepeaterTask(Task):
  def __init__(self, client: Client, config: RepeaterConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config
    self.current_data: RawData | None = None
    self.data_trigger = AsyncTrigger()
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
          self.current_data = data.shallow_copy()
          self.data_trigger.trigger()
        except ValueError:
          if not self.config.fail_closed: await self.out_topic.send(data)
          else: self.current_data = None

  async def _run_sender(self):
    frame_counter = 0
    t0: float | None = None
    delay = hertz_to_fintervall(self.config.rate)

    while True:
      if self.current_data is None:
        await self.data_trigger.wait()
        frame_counter = 0
        t0 = time.time()
      if not self.out_topic.is_paused and self.current_data is not None:
        try:
          msg = self.current_data.shallow_copy()
          set_timestamp_on_message(msg, self.time_sync.time)
          await self.out_topic.send(msg)
        except ValueError: pass
      frame_counter += 1
      wait_time = float(t0 + frame_counter * delay) - time.time()
      if wait_time > 0: await asyncio.sleep(wait_time)

class RepeaterTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="repeater",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic" }],
    default_config=RepeaterConfigBase().model_dump(),
    config_to_output_map=[{ "rate": "rate" }],
    io_mirror=[("in_topic", 0)],
    io_mirror_ignore=["rate"],
    editor_fields=[
      EditorFields.number(key="rate", min_value=0, unit="hz"),
      EditorFields.boolean(key="fail_closed"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return RepeaterTask(await self.create_client(topic_space_id), RepeaterConfig.model_validate(config))
