import unittest
from .shared import TaskTestBase
from streamtasks.tasks.flowdetector import FlowDetectorConfig, FlowDetectorTask, FlowDetectorFailMode
from streamtasks.message import JsonData, NumberMessage
from streamtasks.helpers import get_timestamp_ms
import asyncio

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

  async def _test_fail_mode(self, fail_mode: FlowDetectorFailMode, fm_expected_values):
    async with asyncio.timeout(100):
      async with self.in_topic, self.out_topic, self.signal_topic:
        self.client.start()
        task = self.start_task(fail_mode)
        
        await self.out_topic.set_registered(True)
        await self.signal_topic.set_registered(True)
        await self.in_topic.set_registered(True)

        await self.in_topic.wait_requested()
        await task.signal_topic.wait_requested()
        await task.out_topic.wait_requested()

        await self.in_topic.set_paused(True)
        await self.in_topic.set_paused(False)
        await self.in_topic.send(JsonData({
          "timestamp": get_timestamp_ms(),
          "value": "HEllo"
        }))
        await self.in_topic.send(JsonData({
          "timestamp": get_timestamp_ms(),
        }))

        async def recv_signal():
          data: JsonData = await self.signal_topic.recv_data()
          message = NumberMessage.model_validate(data.data)
          return message.value
        

        # expected_values = [0, 1, 0, 1] + [fm_expected_values[0]] + [fm_expected_values[0]]
        while True: # len(expected_values) > 0:
          if task._task.done(): raise task._task.exception()
          value = await recv_signal()
          # expected_value = expected_values.pop(0)
          print("found value:", value)
          # self.assertEqual(value, expected_value)



  async def test_fail_open(self):
    await self._test_fail_mode(FlowDetectorFailMode.OPEN, [ 1 ])

  async def test_fail_closed(self):
    await self._test_fail_mode(FlowDetectorFailMode.CLOSED, [ 0 ])

if __name__ == '__main__':
  unittest.main()