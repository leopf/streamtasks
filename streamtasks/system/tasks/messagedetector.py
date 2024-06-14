from pydantic import BaseModel, field_serializer
from streamtasks.net.serialization import RawData
from streamtasks.message.utils import get_timestamp_from_message
from streamtasks.message.types import NumberMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from streamtasks.utils import AsyncObservable, AsyncTrigger, TimeSynchronizer
import asyncio
from enum import Enum
from typing import Any

class MessageDetectorFailMode(Enum):
  CLOSED = "closed"
  OPEN = "open"

class MessageDetectorConfigBase(BaseModel):
  fail_mode: MessageDetectorFailMode = MessageDetectorFailMode.OPEN
  time_out: float = 0
  repeat_interval: float = 0

  @field_serializer("fail_mode")
  def ser_fail_mode(self, value: MessageDetectorFailMode): return value.value

class MessageDetectorConfig(MessageDetectorConfigBase):
  in_topic: int
  signal_topic: int

class MessageDetectorState(AsyncObservable):
  def __init__(self, fail_mode: MessageDetectorFailMode) -> None:
    super().__init__()
    self.fail_mode = fail_mode
    self.last_message_invalid = False
    self.input_paused = False
    self.timed_out = False

  @property
  def output_paused(self): return self.input_paused or self.timed_out

  @property
  def signal(self):
    if self.input_paused or self.timed_out: return False
    if self.last_message_invalid:
      if self.fail_mode == MessageDetectorFailMode.CLOSED: return False
      if self.fail_mode == MessageDetectorFailMode.OPEN: return True # to be explicit
      raise ValueError("invalid fail mode!")
    else: return True

class MessageDetectorTask(Task):
  def __init__(self, client: Client, config: MessageDetectorConfig):
    super().__init__(client)
    self.config = config
    self.time_sync = TimeSynchronizer()
    self.in_topic = client.in_topic(config.in_topic)
    self.signal_topic = client.out_topic(config.signal_topic)
    self.message_trigger = AsyncTrigger()
    self.state = MessageDetectorState(self.config.fail_mode)

  async def run(self):
    async with self.in_topic, self.signal_topic, self.in_topic.RegisterContext(), self.signal_topic.RegisterContext():
      self.client.start()
      await asyncio.gather(self.run_main(), self.run_updater(), self.run_watcher())

  async def run_main(self):
    while True:
      data = await self.in_topic.recv_data_control()
      if isinstance(data, TopicControlData): self.state.input_paused = data.paused
      else:
        try:
          self.message_trigger.trigger()
          self.time_sync.update(get_timestamp_from_message(data))
          self.state.last_message_invalid = False
        except ValueError: self.state.last_message_invalid = True

  async def run_watcher(self):
    if self.config.time_out < 0.001: return
    while True:
      try:
        await asyncio.wait_for(self.message_trigger.wait(), self.config.time_out)
        self.state.timed_out = False
      except asyncio.TimeoutError: self.state.timed_out = True

  async def run_updater(self):
    while True:
      await self.signal_topic.send(RawData(NumberMessage(timestamp=self.time_sync.time, value=float(self.state.signal)).model_dump()))
      try: await asyncio.wait_for(self.state.wait_change(), timeout=self.config.repeat_interval or None)
      except asyncio.TimeoutError: pass

class MessageDetectorTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="message detector",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic" }],
    outputs=[{ "label": "signal", "type": "ts", "key": "signal_topic", "content": "number" }],
    default_config=MessageDetectorConfigBase().model_dump(),
    free_inputs=["in_topic"],
    editor_fields=[
      EditorFields.select(key="fail_mode", items=[ (m.value, m.value) for m in MessageDetectorFailMode ]),
      EditorFields.number(key="time_out", label="time out (turns signal=0 when not receiving a message for a specified period. 0=ignore)", min_value=0, unit="s"),
      EditorFields.repeat_interval(min_value=0)
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return MessageDetectorTask(await self.create_client(topic_space_id), MessageDetectorConfig.model_validate(config))
