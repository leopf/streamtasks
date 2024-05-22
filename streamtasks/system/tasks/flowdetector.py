from pydantic import BaseModel, field_serializer
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.utils import get_timestamp_from_message
from streamtasks.net.message.structures import NumberMessage
from streamtasks.net.message.types import TopicControlData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from streamtasks.utils import AsyncObservable, TimeSynchronizer
import asyncio
from enum import Enum
from typing import Any

class FlowDetectorFailMode(Enum):
  CLOSED = "closed"
  OPEN = "open"

class FlowDetectorConfigBase(BaseModel):
  fail_mode: FlowDetectorFailMode = FlowDetectorFailMode.OPEN
  repeat_interval: float = 0

  @field_serializer("fail_mode")
  def ser_fail_mode(self, value: FlowDetectorFailMode): return value.value

class FlowDetectorConfig(FlowDetectorConfigBase):
  in_topic: int
  out_topic: int
  signal_topic: int

class FlowDetectorState(AsyncObservable):
  def __init__(self, fail_mode: FlowDetectorFailMode) -> None:
    super().__init__()
    self.fail_mode = fail_mode
    self.last_message_invalid = False
    self.input_paused = False

  def get_signal(self):
    if self.input_paused: return False
    if self.last_message_invalid:
      if self.fail_mode == FlowDetectorFailMode.CLOSED: return False
      if self.fail_mode == FlowDetectorFailMode.OPEN: return True # to be explicit
      raise ValueError("invalid fail mode!")
    else: return True

class FlowDetectorTask(Task):
  def __init__(self, client: Client, config: FlowDetectorConfig):
    super().__init__(client)
    self.config = config
    self.time_sync = TimeSynchronizer()
    self.in_topic = client.in_topic(config.in_topic)
    self.out_topic = client.out_topic(config.out_topic)
    self.signal_topic = client.out_topic(config.signal_topic)
    self.state = FlowDetectorState(self.config.fail_mode)

  async def run(self):
    async with self.in_topic, self.out_topic, self.signal_topic, self.in_topic.RegisterContext(), \
            self.out_topic.RegisterContext(), self.signal_topic.RegisterContext():
      self.client.start()
      await asyncio.gather(self.run_main(), self.run_updater())

  async def run_main(self):
    while True:
      data = await self.in_topic.recv_data_control()
      if isinstance(data, TopicControlData):
        await self.out_topic.set_paused(data.paused)
        self.state.input_paused = data.paused
      else:
        try:
          self.time_sync.update(get_timestamp_from_message(data))
          self.state.last_message_invalid = False
        except ValueError: self.state.last_message_invalid = True
        finally: await self.out_topic.send(data)

  async def run_updater(self):
    while True:
      await self.signal_topic.send(MessagePackData(NumberMessage(timestamp=self.time_sync.time, value=float(self.state.get_signal())).model_dump()))
      try: await asyncio.wait_for(self.state.wait_change(), timeout=self.config.repeat_interval or None)
      except asyncio.TimeoutError: pass

class FlowDetectorTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="flow detector",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic" }, { "label": "signal", "type": "ts", "key": "signal_topic", "content": "number" }],
    default_config=FlowDetectorConfigBase().model_dump(),
    io_mirror=[("in_topic", 0)],
    editor_fields=[
      EditorFields.select(key="fail_mode", items=[ (m.value, m.value) for m in FlowDetectorFailMode ]),
      EditorFields.repeat_interval(min_value=0)
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return FlowDetectorTask(await self.create_client(topic_space_id), FlowDetectorConfig.model_validate(config))
