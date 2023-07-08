import unittest
from .shared import TaskTestBase
from streamtasks.tasks.flowdetector import FlowDetectorTask, FlowDetectorFailMode
from streamtasks.system.types import TaskDeployment, TaskStream, TaskStreamGroup
from streamtasks.message import JsonData, NumberMessage
from streamtasks.helpers import get_timestamp_ms
import asyncio

class TestFlowDetector(TaskTestBase):

  async def asyncSetUp(self):
    await super().asyncSetUp()
    self.stream_in_topic = self.client.create_provide_tracker()
    await self.stream_in_topic.set_topic(100)
    self.stream_out_topic = self.client.create_subscription_tracker()
    await self.stream_out_topic.set_topic(101, False)
    self.stream_signal_topic = self.client.create_subscription_tracker()
    await self.stream_signal_topic.set_topic(102)


  def get_deployment_config(self, fail_mode: FlowDetectorFailMode): return TaskDeployment(
    id="test_flow_detector",
    task_factory_id="test_factory",
    label="test flow detector",
    config={
      "fail_mode": fail_mode.value,
      "signal_delay": 0.1
    },
    stream_groups=[
      TaskStreamGroup(
        inputs=[ TaskStream(topic_id="input", label="input") ],
        outputs=[
          TaskStream(topic_id="output", label="output"),
          TaskStream(topic_id="signal", label="signal")
        ]
      )
    ],
    topic_id_map={
      "input": self.stream_in_topic.topic,
      "output": self.stream_out_topic.topic,
      "signal": self.stream_signal_topic.topic
    }
  )

  def start_task(self, fail_mode: FlowDetectorFailMode):
    task = FlowDetectorTask(self.worker_client, self.get_deployment_config(fail_mode))
    self.tasks.append(asyncio.create_task(task.start()))
    return task

  async def _test_fail_mode(self, fail_mode: FlowDetectorFailMode, fm_expected_values):
    async with asyncio.timeout(1):
      async with self.client.get_topics_receiver([ self.stream_signal_topic ]) as signal_recv:
        task = self.start_task(fail_mode)
        await task.setup_done.wait()

        await self.stream_out_topic.subscribe()
        await self.stream_in_topic.wait_subscribed()

        await self.stream_in_topic.pause()
        await self.stream_in_topic.resume()

        await self.client.send_stream_data(self.stream_in_topic.topic, JsonData({
          "timestamp": get_timestamp_ms(),
          "value": 1
        }))

        await self.client.send_stream_data(self.stream_in_topic.topic, JsonData({
          "value": 1
        }))

        expected_values = [0, 1, 0, 1] + [fm_expected_values[0]] + [fm_expected_values[0]]
        while len(expected_values) > 0:
          topic_id, data, _ = await signal_recv.recv()
          if data is None: continue
          self.assertEqual(topic_id, self.stream_signal_topic.topic)
          message = NumberMessage.parse_obj(data.data)
          value = message.value
          expected_value = expected_values.pop(0)
          self.assertEqual(value, expected_value)

  async def test_fail_open(self):
    await self._test_fail_mode(FlowDetectorFailMode.FAIL_OPEN, [ 1 ])

  async def test_fail_closed(self):
    await self._test_fail_mode(FlowDetectorFailMode.FAIL_CLOSED, [ 0 ])

if __name__ == '__main__':
  unittest.main()