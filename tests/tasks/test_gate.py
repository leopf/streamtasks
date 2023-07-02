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
    self.stream_gate_topic = self.client.create_provide_tracker()
    await self.stream_gate_topic.set_topic(101)
    self.stream_in_topic = self.client.create_provide_tracker()
    await self.stream_in_topic.set_topic(100)
    self.stream_out_topic = self.client.create_subscription_tracker()
    await self.stream_out_topic.set_topic(102, subscribe=False)

    self.worker_client = Client(conn2[1])
    await self.client.change_addresses([1338])
    await asyncio.sleep(0.001)

  async def asyncTearDown(self):
    self.stop_signal.set()
    for task in self.tasks: await task
  
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
    self.tasks.append(asyncio.create_task(task.async_start(self.stop_signal)))
    return task

  async def send_input_data(self, value: float):
    self.timestamp += 1
    await self.client.send_stream_data(self.stream_in_topic.topic, MessagePackData(NumberMessage(timestamp=self.timestamp, value=value)))
    await asyncio.sleep(0.001)

  async def send_gate_data(self, value: float):
    self.timestamp += 1
    await self.client.send_stream_data(self.stream_gate_topic.topic, MessagePackData(NumberMessage(timestamp=self.timestamp, value=value)))
    await asyncio.sleep(0.001)

  async def wrap_routine(self, fail_mode: GateFailMode, expected_values: list[float], expected_pauses: list[bool]):
    gate = self.start_gate(fail_mode)
    async with self.client.get_topics_receiver([ self.stream_out_topic ]) as out_reciever:
      await self.stream_out_topic.subscribe()

      await self.send_input_data(1)
      await self.send_gate_data(0)
      await self.send_input_data(2)
      await self.send_gate_data(1)
      await self.send_input_data(3)
      await self.send_gate_data(0)
      await self.stream_gate_topic.pause()
      await self.send_input_data(4)
      await self.stream_gate_topic.resume()
      await self.send_gate_data(1)
      await self.send_input_data(5)
      await self.stream_in_topic.pause()
      await self.stream_in_topic.resume()
      await self.send_input_data(6)
      await self.client.send_stream_data(self.stream_gate_topic.topic, MessagePackData({ "value": 0.5 }))
      await self.send_input_data(7)
      await self.send_gate_data(0)
      await self.client.send_stream_data(self.stream_gate_topic.topic, MessagePackData({ "value": 0.5 }))
      await self.send_input_data(8)
      await self.send_gate_data(1)

      # await self.stream_out_topic.unsubscribe()
      # await asyncio.wait_for(self.stream_in_topic.wait_subscribed(self.stop_signal, False), 10000)
      # await self.stream_out_topic.subscribe()
      # await asyncio.wait_for(self.stream_in_topic.wait_subscribed(self.stop_signal), 10000)


      expected_values = expected_values.copy()
      expected_pauses = expected_pauses.copy()

      while len(expected_values) > 0 or len(expected_pauses) > 0:
        topic_id, data, control = await out_reciever.recv()
        self.assertEqual(topic_id, self.stream_out_topic.topic)
        if control:
          print(control.paused, expected_values)
          expected_pause = expected_pauses.pop(0)
          self.assertEqual(control.paused, expected_pause)
        if data:
          print("value: ", data.data.value, expected_values)
          expected_value = expected_values.pop(0)
          self.assertEqual(data.data.value, expected_value)

  async def test_gate_fail_open(self):
    await self.wrap_routine(GateFailMode.FAIL_OPEN, [1, 3, 4, 5, 6, 7, 8], [True, False, True, False, True, False])

  async def test_gate_fail_closed(self):
    await self.wrap_routine(GateFailMode.FAIL_CLOSED, [3, 5, 6], [True, False, True, False, True, False])

  async def test_gate_passive(self):
    await self.wrap_routine(GateFailMode.PASSIVE, [1, 3, 5, 6, 7], [True, False, True, False, True, False, True, False])

if __name__ == "__main__":
  unittest.main()