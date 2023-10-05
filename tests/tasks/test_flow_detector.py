from enum import Enum
from typing import Iterator
import unittest
from .shared import TaskTestBase
from streamtasks.tasks.flowdetector import FlowDetectorConfig, FlowDetectorState, FlowDetectorTask, FlowDetectorFailMode
from streamtasks.message import JsonData, NumberMessage
from streamtasks.helpers import get_timestamp_ms
import asyncio
import itertools
import random

class FDEvent(Enum):
  pause = "pause"
  unpause = "unpause"
  valid_data = "valid data"
  invalid_data = "invalid data"

"""
This class simulates the expected behavior of the flow detector
"""
class FDSim:
  def __init__(self, fail_mode: FlowDetectorFailMode) -> None:
    self.state = FlowDetectorState()
    self.fail_mode = fail_mode
    self._signals: list[float] = [not self.state.get_signal(self.fail_mode)]

  @property
  def signals(self): return self._signals[1:] # ignore initial value

  def event(self, event: FDEvent):
    if event == FDEvent.pause: 
      self.state.input_paused = True
    if event == FDEvent.unpause: 
      self.state.input_paused = False
    if event == FDEvent.valid_data:
      self.state.last_message_invalid = False 
    if event == FDEvent.invalid_data:
      self.state.last_message_invalid = True
    self.update_signal()

  def update_signal(self): 
    new_signal = self.state.get_signal(self.fail_mode)
    if self._signals[-1] != new_signal: self._signals.append(new_signal)
  
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

  def generate_events(self) -> Iterator[FDEvent]:
    subsequences = list(itertools.permutations(list(FDEvent)))
    rng = random.Random(42)
    rng.shuffle(subsequences)
    for seq in subsequences:
      for event in seq:
        yield event

  async def _test_fail_mode(self, fail_mode: FlowDetectorFailMode):
    async with asyncio.timeout(10):
      async with self.in_topic, self.out_topic, self.signal_topic:
        self.client.start()
        task = self.start_task(fail_mode)
        
        await self.out_topic.set_registered(True)
        await self.signal_topic.set_registered(True)
        await self.in_topic.set_registered(True)

        await self.in_topic.wait_requested()
        await task.signal_topic.wait_requested()
        await task.out_topic.wait_requested()
        
        sim = FDSim(fail_mode)
        for event in self.generate_events():
          sim.event(event)
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

        expected_values = list(float(s) for s in sim._signals)

        while len(expected_values) > 0:
          data: JsonData = await self.signal_topic.recv_data()
          message = NumberMessage.model_validate(data.data)
          self.assertEqual(message.value, expected_values.pop(0))
          print(f"{len(expected_values)} to go")

  async def test_fail_open(self):
    await self._test_fail_mode(FlowDetectorFailMode.OPEN)

  async def test_fail_closed(self):
    await self._test_fail_mode(FlowDetectorFailMode.CLOSED)

if __name__ == '__main__':
  unittest.main()