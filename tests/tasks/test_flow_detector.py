import unittest
from .shared import TaskTestBase
from streamtasks.tasks.flowdetector import FlowDetectorTask, FlowDetectorFailMode
from streamtasks.system.types import DeploymentTask, TaskInputStream, TaskOutputStream, TaskStreamGroup
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


  def get_deployment_config(self, fail_mode: FlowDetectorFailMode): return DeploymentTask(
    task_factory_id="test_factory",
    label="test flow detector",
    config={
      "fail_mode": fail_mode.value,
      "signal_delay": 1
    },
    stream_groups=[
      TaskStreamGroup(
        inputs=[ TaskInputStream(topic_id="input", label="input") ],
        outputs=[
          TaskOutputStream(topic_id="output", label="output"),
          TaskOutputStream(topic_id="signal", label="signal")
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
    async with asyncio.timeout(10):
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

        async def recv_value():
          topic_id, data, _ = await signal_recv.recv()
          if data is None: return None
          self.assertEqual(topic_id, self.stream_signal_topic.topic)
          message = NumberMessage.model_validate(data.data)
          return message.value

        expected_values = [0, 1, 0, 1] + [fm_expected_values[0]] + [fm_expected_values[0]]
        while len(expected_values) > 0:
          value = await recv_value()
          if value is None: continue
          print(f"got: {value}")
          expected_value = expected_values.pop(0)
          print(f"expected: {expected_value}, got: {value}")
          self.assertEqual(value, expected_value)

  async def test_fail_open(self):
    await self._test_fail_mode(FlowDetectorFailMode.FAIL_OPEN, [ 1 ])

  async def test_fail_closed(self):
    await self._test_fail_mode(FlowDetectorFailMode.FAIL_CLOSED, [ 0 ])

if __name__ == '__main__':
  unittest.main()