from enum import Enum
from typing import Iterator
import unittest
from .shared import TaskTestBase
from streamtasks.tasks.flowdetector import FlowDetectorConfig, FlowDetectorTask, FlowDetectorFailMode
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
    self.signals: list[float] = []
    self.fail_mode = fail_mode
    self.paused = False
    self.data_invalid = False
    self.push_signal(fail_mode == FlowDetectorFailMode.OPEN)

  def event(self, event: FDEvent):
    if event == FDEvent.pause: 
      self.push_signal(False)
      self.paused = True
    if event == FDEvent.unpause and not self.data_invalid: 
      self.push_signal(True)
      self.paused = False
    if event == FDEvent.valid_data and self.data_invalid:
      self.data_invalid = False
      if not self.paused: self.push_signal(True)
    if event == FDEvent.invalid_data:
      self.data_invalid = True
      if self.fail_mode == FlowDetectorFailMode.CLOSED: 
        self.push_signal(False)
      if self.fail_mode == FlowDetectorFailMode.OPEN and not self.paused: 
        self.push_signal(True)

  def push_signal(self, v): 
    if len(self.signals) == 0 or v != self.signals[-1]: self.signals.append(v)

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
    possible_events = list(FDEvent)
    subsequences = list(itertools.combinations(possible_events, len(possible_events)))
    rng = random.Random(42)
    rng.shuffle(subsequences)
    for seq in subsequences:
      for event in seq:
        yield event

  async def _test_fail_mode(self, fail_mode: FlowDetectorFailMode):
    async with asyncio.timeout(1):
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

        expected_values = list(float(s) for s in sim.signals)

        while len(expected_values) > 0:
          data: JsonData = await self.signal_topic.recv_data()
          message = NumberMessage.model_validate(data.data)
          self.assertEqual(message.value, expected_values.pop(0))

  async def test_fail_open(self):
    await self._test_fail_mode(FlowDetectorFailMode.OPEN)

  async def test_fail_closed(self):
    await self._test_fail_mode(FlowDetectorFailMode.CLOSED)

  async def test_fail_passive(self):
    await self._test_fail_mode(FlowDetectorFailMode.PASSIVE)

if __name__ == '__main__':
  unittest.main()