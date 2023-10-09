import unittest
from streamtasks.net.types import TopicControlData
from streamtasks.tasks.gate import GateConfig, GateTask, GateFailMode
from streamtasks.system.types import DeploymentTask, TaskInputStream, TaskOutputStream, TaskStreamGroup
from streamtasks.message import NumberMessage, MessagePackData
import asyncio

from .shared import TaskTestBase

class TestGate(TaskTestBase):
  async def asyncSetUp(self):
    await super().asyncSetUp()
    # since we are outside the task the in/outs are flipped
    self.gate_topic = self.client.out_topic(101)
    self.in_topic = self.client.out_topic(100)
    self.out_topic = self.client.in_topic(102)

  def start_gate(self, fail_mode: GateFailMode):
    task = GateTask(self.worker_client, GateConfig(
      fail_mode=fail_mode,
      in_topic=self.in_topic.topic,
      gate_topic=self.gate_topic.topic,
      out_topic=self.out_topic.topic,
    ))
    self.tasks.append(asyncio.create_task(task.start()))
    return task

  async def send_input_data(self, value: float):
    self.timestamp += 1
    await self.in_topic.send(MessagePackData(NumberMessage(timestamp=self.timestamp, value=value).model_dump()))
    await asyncio.sleep(0.001)

  async def send_gate_data(self, value: float):
    self.timestamp += 1
    await self.gate_topic.send(MessagePackData(NumberMessage(timestamp=self.timestamp, value=value).model_dump()))
    await asyncio.sleep(0.001)

  async def send_gate_pause(self, paused: bool):
    self.timestamp += 1
    await self.gate_topic.set_paused(paused)
    await asyncio.sleep(0.001)

  async def send_input_pause(self, paused: bool):
    self.timestamp += 1
    await self.in_topic.set_paused(paused)
    await asyncio.sleep(0.001)

  async def _test_fail_mode(self, fail_mode: GateFailMode, expected_values: list[float], expected_pauses: list[bool]):
    async with asyncio.timeout(10), self.in_topic, self.gate_topic, self.out_topic:
      self.client.start()
      gate = self.start_gate(fail_mode)
      await self.out_topic.set_registered(True)
      await self.in_topic.set_registered(True)
      await self.gate_topic.set_registered(True)
      await self.in_topic.wait_requested()
      await self.gate_topic.wait_requested()

      await self.send_input_data(1)
      await self.send_gate_data(0)
      await self.send_input_data(2)
      await self.send_gate_data(1)
      await self.send_input_data(3)
      await self.send_gate_data(0)
      await self.send_gate_pause(True)
      await self.send_input_data(4)
      await self.send_gate_pause(False)
      await self.send_gate_data(1)
      await self.send_input_data(5)
      await self.send_input_pause(True)
      await self.send_input_pause(False)
      await self.send_input_data(6)
      self.timestamp += 1
      await self.client.send_stream_data(self.gate_topic.topic, MessagePackData({ "timestamp": self.timestamp }))
      await self.send_input_data(7)
      await self.send_gate_data(0)
      self.timestamp += 1
      await self.client.send_stream_data(self.gate_topic.topic, MessagePackData({ "timestamp": self.timestamp }))
      await self.send_input_data(8)
      await self.send_gate_data(1)

      expected_values = expected_values.copy()
      expected_pauses = expected_pauses.copy()

      while len(expected_values) > 0 or len(expected_pauses) > 0:
        data = await self.out_topic.recv_data_control()
        if isinstance(data, TopicControlData):
          expected_pause = expected_pauses.pop(0)
          self.assertEqual(data.paused, expected_pause)
        else:
          value = data.data["value"]
          expected_value = expected_values.pop(0)
          self.assertEqual(value, expected_value)

  async def test_gate_fail_open(self):
    await self._test_fail_mode(
      GateFailMode.OPEN,
      [1, 3, 4, 5, 6, 7, 8],
      [True, False, True, False]
    )

  async def test_gate_fail_closed(self):
    await self._test_fail_mode(
      GateFailMode.CLOSED,
      [3, 5, 6],
      [True, False, True, False]
    )

if __name__ == "__main__":
  unittest.main()