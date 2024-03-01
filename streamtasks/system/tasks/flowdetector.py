from dataclasses import dataclass
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.utils import get_timestamp_from_message
from streamtasks.net.message.structures import NumberMessage
from streamtasks.net.message.types import TopicControlData
from streamtasks.system.task import Task
from streamtasks.client import Client
from streamtasks.utils import AsyncObservable, TimeSynchronizer
import asyncio
from enum import Enum
from typing import Optional


class FlowDetectorFailMode(Enum):
  CLOSED = "closed"
  OPEN = "open"


@dataclass
class FlowDetectorConfig:
  in_topic: int
  out_topic: int
  signal_topic: int
  fail_mode: FlowDetectorFailMode
  signal_delay: Optional[float] = None


class FlowDetectorState(AsyncObservable):
  last_message_invalid: bool
  input_paused: bool

  def __init__(self) -> None:
    super().__init__()
    self.last_message_invalid = False
    self.input_paused = False

  def get_signal(self, fail_mode: FlowDetectorFailMode):
    if self.input_paused: return False
    if self.last_message_invalid:
      if fail_mode == FlowDetectorFailMode.CLOSED: return False
      if fail_mode == FlowDetectorFailMode.OPEN: return True # to be explicit
    else:
      return True


class FlowDetectorTask(Task):
  def __init__(self, client: Client, config: FlowDetectorConfig):
    super().__init__(client)
    self.time_sync = TimeSynchronizer()
    self.in_topic = client.in_topic(config.in_topic)
    self.out_topic = client.out_topic(config.out_topic)
    self.signal_topic = client.out_topic(config.signal_topic)

    self.fail_mode = config.fail_mode
    self.signal_delay = config.signal_delay
    self.state = FlowDetectorState()
    self.current_signal = self.state.get_signal(self.fail_mode) # make sure the initial state is sent

  async def run(self):
    tasks: list[asyncio.Task] = []
    try:
      async with self.in_topic, self.out_topic, self.signal_topic, self.in_topic.RegisterContext(), \
              self.out_topic.RegisterContext(), self.signal_topic.RegisterContext():

        tasks.append(asyncio.create_task(self.run_main()))
        tasks.append(asyncio.create_task(self.run_updater()))
        if self.signal_delay: tasks.append(asyncio.create_task(self.run_lighthouse()))

        self.client.start()
        await asyncio.gather(*tasks)
    finally:
      for task in tasks: task.cancel()

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
      await asyncio.sleep(0.001)

  async def run_updater(self):
    while True:
      new_signal = self.state.get_signal(self.fail_mode)
      if new_signal != self.current_signal:
        self.current_signal = new_signal
        await self.send_current_signal()
      await self.state.wait_change()

  async def run_lighthouse(self):
    while True:
      await asyncio.sleep(self.signal_delay)
      await self.send_current_signal()

  async def send_current_signal(self):
    await self.signal_topic.send(MessagePackData(NumberMessage(timestamp=self.time_sync.time, value=float(self.current_signal)).model_dump()))