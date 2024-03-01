from dataclasses import dataclass

from pydantic import ValidationError
from streamtasks.client.topic import InTopicSynchronizer
from streamtasks.utils import AsyncObservable
from streamtasks.net.message.structures import NumberMessage
from streamtasks.net.message.types import TopicControlData
from streamtasks.system.task import Task
from streamtasks.client import Client
import asyncio
from enum import Enum


class GateFailMode(Enum):
  CLOSED = "closed"
  OPEN = "open"


@dataclass
class GateConfig:
  fail_mode: GateFailMode
  gate_topic: int
  in_topic: int
  out_topic: int
  synchronized: bool = True


class GateState(AsyncObservable):
  def __init__(self) -> None:
    super().__init__()
    self.gate_paused: bool = False
    self.gate_errored: bool = False
    self.input_paused: bool = False
    self.gate_value: bool = True

  def get_open(self, fail_mode: GateFailMode):
    if self.input_paused or not self.gate_value: return False
    if fail_mode == GateFailMode.CLOSED and (self.gate_paused or self.gate_errored): return False
    return True
  def get_output_paused(self, fail_mode: GateFailMode): return not self.get_open(fail_mode)


class GateTask(Task):
  def __init__(self, client: Client, config: GateConfig):
    super().__init__(client)
    if config.synchronized:
      sync = InTopicSynchronizer()
      self.in_topic = self.client.sync_in_topic(config.in_topic, sync)
      self.gate_topic = self.client.sync_in_topic(config.gate_topic, sync)
      self.out_topic = self.client.out_topic(config.out_topic)
    else:
      self.in_topic = self.client.in_topic(config.in_topic)
      self.gate_topic = self.client.in_topic(config.gate_topic)
      self.out_topic = self.client.out_topic(config.out_topic)
    self.state = GateState()
    self.fail_mode = config.fail_mode

  async def run(self):
    tasks: list[asyncio.Task] = []
    try:
      async with self.in_topic, self.gate_topic, self.out_topic, self.in_topic.RegisterContext(), \
              self.gate_topic.RegisterContext(), self.out_topic.RegisterContext():

        tasks.append(asyncio.create_task(self.run_gate_recv()))
        tasks.append(asyncio.create_task(self.run_in_recv()))
        tasks.append(asyncio.create_task(self.run_out_pauser()))

        self.client.start()
        await asyncio.gather(*tasks)
    finally:
      for task in tasks: task.cancel()

  async def run_gate_recv(self):
    while True:
      data = await self.gate_topic.recv_data_control()
      if isinstance(data, TopicControlData):
        self.state.gate_paused = data.paused
      else:
        try:
          msg = NumberMessage.model_validate(data.data)
          self.state.gate_value = msg.value > 0.5
          self.state.gate_errored = False
        except ValidationError:
          self.state.gate_errored = True
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
