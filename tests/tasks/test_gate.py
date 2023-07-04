import unittest
from streamtasks.tasks.gate import GateTask, GateFailMode
from streamtasks.system.types import TaskDeployment, TaskStream, TaskStreamGroup
from streamtasks.client import Client
from streamtasks.comm import Switch, create_local_cross_connector
from streamtasks.comm.types import TopicControlData
from streamtasks.message import NumberMessage, StringMessage, MessagePackData
import asyncio
import itertools

from .shared import TaskTestBase

class TestGate(TaskTestBase):
  async def asyncSetUp(self):
    await super().asyncSetUp()
    self.stream_gate_topic = self.client.create_provide_tracker()
    await self.stream_gate_topic.set_topic(101)
    self.stream_in_topic = self.client.create_provide_tracker()
    await self.stream_in_topic.set_topic(100)
    self.stream_out_topic = self.client.create_subscription_tracker()
    await self.stream_out_topic.set_topic(102, subscribe=False)

  def get_deployment_config(self, fail_mode: GateFailMode): return TaskDeployment(
      id="test_gate",
      task_factory_id="test_factory",
      label="test gate",
      config={ "fail_mode": fail_mode.value },
      stream_groups=[
        TaskStreamGroup(
          inputs=[ 
            TaskStream(topic_id="input", label="input"),
            TaskStream(topic_id="gate", label="gate")
          ],
          outputs=[ TaskStream(topic_id="output", label="output") ]
        )
      ],
      topic_id_map={
        "input": self.stream_in_topic.topic,
        "gate": self.stream_gate_topic.topic,
        "output": self.stream_out_topic.topic
      }
    )

  def start_gate(self, fail_mode: GateFailMode):
    task = GateTask(self.worker_client, self.get_deployment_config(fail_mode))
    self.tasks.append(asyncio.create_task(task.start()))
    return task

  async def send_input_data(self, value: float):
    self.timestamp += 1
    await self.client.send_stream_data(self.stream_in_topic.topic, MessagePackData(NumberMessage(timestamp=self.timestamp, value=value).dict()))
    await asyncio.sleep(0.001)

  async def send_gate_data(self, value: float):
    self.timestamp += 1
    await self.client.send_stream_data(self.stream_gate_topic.topic, MessagePackData(NumberMessage(timestamp=self.timestamp, value=value).dict()))
    await asyncio.sleep(0.001)

  async def send_gate_pause(self, paused: bool):
    self.timestamp += 1
    await self.stream_gate_topic.set_paused(paused)
    await asyncio.sleep(0.001)

  async def send_input_pause(self, paused: bool):
    self.timestamp += 1
    await self.stream_in_topic.set_paused(paused)
    await asyncio.sleep(0.001)

  async def _test_fail_mode(self, fail_mode: GateFailMode, expected_values: list[float], expected_pauses: list[bool]):
    async with asyncio.timeout(1):
      gate = self.start_gate(fail_mode)
      async with self.client.get_topics_receiver([ self.stream_out_topic ]) as out_reciever:
        await self.stream_out_topic.subscribe()
        await self.stream_in_topic.wait_subscribed()
        await self.stream_gate_topic.wait_subscribed()

        await self.send_input_data(1)
        if 1 not in expected_values: await self.stream_in_topic.wait_subscribed(subscribed=False)
        await self.send_gate_data(0)
        await self.stream_in_topic.wait_subscribed(subscribed=False)
        await self.send_input_data(2)
        await self.stream_in_topic.wait_subscribed(subscribed=False)
        await self.send_gate_data(1)
        await self.stream_in_topic.wait_subscribed(subscribed=True)
        await self.send_input_data(3)
        await self.send_gate_data(0)
        await self.send_gate_pause(True)
        await self.send_input_data(4)
        if 3 not in expected_values: await self.stream_in_topic.wait_subscribed(subscribed=False)
        await self.send_gate_pause(False)
        await self.send_gate_data(1)
        await self.stream_in_topic.wait_subscribed(subscribed=True)
        await self.send_input_data(5)
        await self.send_input_pause(True)
        await self.send_input_pause(False)
        await self.send_input_data(6)
        await self.client.send_stream_data(self.stream_gate_topic.topic, MessagePackData({ "value": 0.5 }))
        await self.send_input_data(7)
        if 7 not in expected_values: await self.stream_in_topic.wait_subscribed(subscribed=False)
        await self.send_gate_data(0)
        await self.client.send_stream_data(self.stream_gate_topic.topic, MessagePackData({ "value": 0.5 }))
        await self.send_input_data(8)
        if 8 not in expected_values: await self.stream_in_topic.wait_subscribed(subscribed=False)
        await self.send_gate_data(1)

        expected_values = expected_values.copy()
        expected_pauses = expected_pauses.copy()

        while len(expected_values) > 0 or len(expected_pauses) > 0:
          topic_id, data, control = await out_reciever.recv()
          self.assertEqual(topic_id, self.stream_out_topic.topic)
          if control:
            expected_pause = expected_pauses.pop(0)
            self.assertEqual(control.paused, expected_pause)
          if data:
            value = data.data["value"]
            expected_value = expected_values.pop(0)
            self.assertEqual(value, expected_value)

  async def test_gate_fail_open(self):
    await self._test_fail_mode(
      GateFailMode.FAIL_OPEN,
      [1, 3, 4, 5, 6, 7, 8],
      [True, False, True, False]
    )

  async def test_gate_fail_closed(self):
    await self._test_fail_mode(
      GateFailMode.FAIL_CLOSED,
      [3, 5, 6],
      [True, False, True, False, True, False]
    )

  async def test_gate_passive(self):
    await self._test_fail_mode(
      GateFailMode.PASSIVE,
      [1, 3, 5, 6, 7],
      [True, False, True, False, True, False, True, False]
    )

  async def test_unsubscribe(self):
    async with asyncio.timeout(1):
      gate = self.start_gate(GateFailMode.PASSIVE)
      async with self.client.get_topics_receiver([ self.stream_out_topic ]) as out_reciever:
        await self.stream_out_topic.subscribe()

        await self.stream_in_topic.wait_subscribed()
        await self.stream_gate_topic.wait_subscribed()
        await self.stream_out_topic.unsubscribe()

        await self.stream_in_topic.wait_subscribed(subscribed=False)
        await self.stream_gate_topic.wait_subscribed(subscribed=False)

if __name__ == "__main__":
  setup()
  unittest.main()