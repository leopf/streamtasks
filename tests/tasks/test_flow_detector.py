from enum import Enum
from typing import Any
import unittest

from tests.sim import Simulator
from .shared import TaskTestBase
from streamtasks.tasks.flowdetector import FlowDetectorConfig, FlowDetectorState, FlowDetectorTask, FlowDetectorFailMode
from streamtasks.message import JsonData, NumberMessage
from streamtasks.helpers import get_timestamp_ms
import asyncio


class FDEvent(Enum):
  pause = "pause"
  unpause = "unpause"
  valid_data = "valid data"
  invalid_data = "invalid data"


# This class simulates the expected behavior of the flow detector
class FlowDetectorSim(Simulator):
  def __init__(self, fail_mode: FlowDetectorFailMode) -> None:
    super().__init__()
    self.state = FlowDetectorState()
    self.fail_mode = fail_mode

  def update_state(self, event: FDEvent):
    if event == FDEvent.pause:
      self.state.input_paused = True
    if event == FDEvent.unpause:
      self.state.input_paused = False
    if event == FDEvent.valid_data:
      self.state.last_message_invalid = False
    if event == FDEvent.invalid_data:
      self.state.last_message_invalid = True

  def get_output(self) -> dict[str, Any]: return { "signal": self.state.get_signal(self.fail_mode) }
  def get_state(self) -> dict[str, Any]: return self.state.as_dict()


class TestFlowDetector(TaskTestBase):

  async def asyncSetUp(self):
    await super().asyncSetUp()
    self.in_topic = self.client.out_topic(100)
    self.out_topic = self.client.in_topic(101)
    self.signal_topic = self.client.in_topic(102)

  def start_task(self, fail_mode: FlowDetectorFailMode):
    task = FlowDetectorTask(self.worker_client, FlowDetectorConfig(
      fail_mode=fail_mode,
      in_topic=self.in_topic.topic,
      out_topic=self.out_topic.topic,
      signal_topic=self.signal_topic.topic,
    ))
    self.tasks.append(asyncio.create_task(task.start()))
    return task

  async def _test_fail_mode(self, fail_mode: FlowDetectorFailMode):
    async with asyncio.timeout(1000), self.in_topic, self.out_topic, self.signal_topic:
      self.client.start()
      task = self.start_task(fail_mode)

      await self.out_topic.set_registered(True)
      await self.signal_topic.set_registered(True)
      await self.in_topic.set_registered(True)

      await self.in_topic.wait_requested()
      await task.signal_topic.wait_requested()
      await task.out_topic.wait_requested()

      sim = FlowDetectorSim(fail_mode)
      sim.eout_changed()
      for event in sim.generate_events(list(FDEvent)):
        sim.on_event(event)
        if event == FDEvent.pause:
          await self.in_topic.set_paused(True)
        if event == FDEvent.unpause:
          await self.in_topic.set_paused(False)
        if event == FDEvent.valid_data:
          await self.in_topic.send(JsonData({
            "timestamp": get_timestamp_ms(),
          }))
        if event == FDEvent.invalid_data:
          await self.in_topic.send(JsonData({
            "value": "hello"
          }))
        if sim.eout_changed():
          data: JsonData = await sim.wait_or_fail(self.signal_topic.recv_data(), 1)
          message = NumberMessage.model_validate(data.data)
          sim.on_output({"signal": message.value > 0.5})
        else: sim.on_idle()

  async def test_fail_open(self):
    await self._test_fail_mode(FlowDetectorFailMode.OPEN)

  async def test_fail_closed(self):
    await self._test_fail_mode(FlowDetectorFailMode.CLOSED)


if __name__ == '__main__':
  unittest.main()