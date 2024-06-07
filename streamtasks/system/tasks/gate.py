
from typing import Any
from pydantic import BaseModel, ValidationError, field_serializer
from streamtasks.client.topic import PrioritizedSequentialInTopicSynchronizer
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.utils import AsyncObservable
from streamtasks.message.types import NumberMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
import asyncio
from enum import Enum


class GateFailMode(Enum):
  CLOSED = "closed"
  OPEN = "open"

class GateConfigBase(BaseModel):
  fail_mode: GateFailMode = GateFailMode.OPEN
  synchronized: bool = True
  initial_control: bool = False

  @field_serializer("fail_mode")
  def ser_fail_mode(self, value: GateFailMode): return value.value

class GateConfig(GateConfigBase):
  control_topic: int
  in_topic: int
  out_topic: int

class GateState(AsyncObservable):
  def __init__(self, control: bool) -> None:
    super().__init__()
    self.control: bool = control
    self.control_paused: bool = False
    self.control_errored: bool = False
    self.input_paused: bool = False

  def get_open(self, fail_mode: GateFailMode):
    if self.input_paused or not self.control: return False
    if fail_mode == GateFailMode.CLOSED and (self.control_paused or self.control_errored): return False
    return True
  def get_output_paused(self, fail_mode: GateFailMode): return not self.get_open(fail_mode)


class GateTask(Task):
  def __init__(self, client: Client, config: GateConfig):
    super().__init__(client)
    if config.synchronized:
      sync = PrioritizedSequentialInTopicSynchronizer()
      # make sure control is received before in data is (if timestamps match)
      sync.set_priority(config.control_topic, 1)
      sync.set_priority(config.in_topic, 0)
      self.in_topic = self.client.sync_in_topic(config.in_topic, sync)
      self.control_topic = self.client.sync_in_topic(config.control_topic, sync)
    else:
      self.in_topic = self.client.in_topic(config.in_topic)
      self.control_topic = self.client.in_topic(config.control_topic)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.state = GateState(config.initial_control)
    self.fail_mode = config.fail_mode

  async def run(self):
    async with self.in_topic, self.control_topic, self.out_topic, self.in_topic.RegisterContext(), \
            self.control_topic.RegisterContext(), self.out_topic.RegisterContext():
      self.client.start()
      await asyncio.gather(self.run_control_recv(), self.run_in_recv(), self.run_out_pauser())

  async def run_control_recv(self):
    while True:
      data = await self.control_topic.recv_data_control()
      if isinstance(data, TopicControlData):
        self.state.control_paused = data.paused
      else:
        try:
          msg = NumberMessage.model_validate(data.data)
          self.state.control = msg.value > 0.5
          self.state.control_errored = False
        except ValidationError:
          self.state.control_errored = True
  async def run_out_pauser(self):
    while True:
      await self.out_topic.set_paused(self.state.get_output_paused(self.fail_mode))
      await self.state.wait_change()
  async def run_in_recv(self):
    while True:
      data = await self.in_topic.recv_data_control()
      if isinstance(data, TopicControlData):
        self.state.input_paused = data.paused
      else:
        if self.state.get_open(self.fail_mode):
          await self.out_topic.send(data)

class GateTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="gate",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic" }, { "label": "control", "type": "ts", "content": "number", "key": "control_topic" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic" }],
    default_config=GateConfigBase().model_dump(),
    io_mirror=[("in_topic", 0)],
    editor_fields=[
      EditorFields.select(key="fail_mode", items=[ (m.value, m.value) for m in GateFailMode ]),
      EditorFields.boolean(key="initial_control", label="initial control (initial state of the gate)"),
      EditorFields.boolean(key="synchronized")
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return GateTask(await self.create_client(topic_space_id), GateConfig.model_validate(config))
