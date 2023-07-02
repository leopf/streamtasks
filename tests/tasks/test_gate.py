import unittest
from streamtasks.tasks.gate import GateTask, GateFailMode
from streamtasks.system.types import TaskDeployment, TaskStream, TaskStreamGroup
from streamtasks.client import Client
from streamtasks.comm import Switch, create_local_cross_connector, create_switch_processing_task
from streamtasks.comm.types import TopicControlData
from streamtasks.message import NumberMessage, StringMessage, MessagePackData
import asyncio
import itertools

class TestGate(unittest.IsolatedAsyncioTestCase):
  client: Client
  worker_client: GateTask

  stop_signal: asyncio.Event
  tasks: list[asyncio.Task]

  stream_in_topic_id = 100
  stream_gate_topic_id = 101
  stream_out_topic_id = 102

  async def asyncSetUp(self):
    self.stop_signal = asyncio.Event()
    self.tasks = []

    conn1 = create_local_cross_connector(raw=False)
    conn2 = create_local_cross_connector(raw=False)

    switch = Switch()
    await switch.add_connection(conn1[0])
    await switch.add_connection(conn2[0])
    self.timestamp = 0
    self.tasks.append(create_switch_processing_task(switch, self.stop_signal))

    self.client = Client(conn1[1])
    await self.client.provide([ self.stream_in_topic_id, self.stream_gate_topic_id ])
    self.worker_client = Client(conn2[1])
    await self.client.change_addresses([1338])
    await asyncio.sleep(0.001)

  async def asyncTearDown(self):
    self.stop_signal.set()
    for task in self.tasks: await task
  
  def start_gate(self, fail_mode: GateFailMode):
    task = GateTask(self.worker_client, TaskDeployment(
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
        "input": self.stream_in_topic_id,
        "gate": self.stream_gate_topic_id,
        "output": self.stream_out_topic_id
      }
    ))
    self.tasks.append(asyncio.create_task(task.async_start(self.stop_signal)))
    return task

  async def send_input_data(self, value: float):
    self.timestamp += 1
    await self.client.send_stream_data(self.stream_in_topic_id, MessagePackData(NumberMessage(timestamp=self.timestamp, value=value)))
    await asyncio.sleep(0.001)

  async def send_gate_data(self, value: float):
    self.timestamp += 1
    await self.client.send_stream_data(self.stream_gate_topic_id, MessagePackData(NumberMessage(timestamp=self.timestamp, value=value)))
    await asyncio.sleep(0.001)

  async def send_input_pause(self, paused: bool):
    self.timestamp += 1
    await self.client.send_stream_control(self.stream_in_topic_id, TopicControlData(paused=paused))
    await asyncio.sleep(0.001)
  
  async def send_gate_pause(self, paused: bool):
    self.timestamp += 1
    await self.client.send_stream_control(self.stream_gate_topic_id, TopicControlData(paused=paused))
    await asyncio.sleep(0.001)

  async def wrap_routine(self, fail_mode: GateFailMode, expected_values: list[float], expected_pauses: list[bool]):
    gate = self.start_gate(fail_mode)
    
    async with self.client.get_topics_receiver([ self.stream_out_topic_id ]) as out_reciever:
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
      await self.client.send_stream_data(self.stream_gate_topic_id, MessagePackData({ "value": 0.5 }))
      await self.send_input_data(7)
      await self.send_gate_data(0)
      await self.client.send_stream_data(self.stream_gate_topic_id, MessagePackData({ "value": 0.5 }))
      await self.send_input_data(8)

      expected_values = expected_values.copy()
      expected_pauses = expected_pauses.copy()

      while len(expected_values) > 0 or len(expected_pauses) > 0:
        topic_id, data, control = await out_reciever.recv()
        self.assertEqual(topic_id, self.stream_out_topic_id)
        if control:
          print(control.paused, expected_values)
          expected_pause = expected_pauses.pop(0)
          self.assertEqual(control.paused, expected_pause)
        if data:
          print("value: ", data.data.value, expected_values)
          expected_value = expected_values.pop(0)
          self.assertEqual(topic_id, self.stream_out_topic_id)
          self.assertEqual(data.data.value, expected_value)

  async def test_gate_fail_open(self):
    await self.wrap_routine(GateFailMode.FAIL_OPEN, [1, 3, 4, 5, 6, 7, 8], [True, False, True, False])

  async def test_gate_fail_closed(self):
    await self.wrap_routine(GateFailMode.FAIL_CLOSED, [3, 5, 6], [True, False, True, False, True, False])

  async def test_gate_passive(self):
    await self.wrap_routine(GateFailMode.PASSIVE, [1, 3, 5, 6, 7], [True, False, True, False, True, False])

if __name__ == "__main__":
  unittest.main()