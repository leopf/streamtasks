import unittest
from streamtasks.worker import Worker
from streamtasks.node import *
from streamtasks.message.data import MessagePackData
from streamtasks.client import *
from streamtasks.system import *
import asyncio
from pydantic import parse_obj_as
import json

class CounterEmitTask(Task):
  def __init__(self, client: Client, deployment: TaskDeployment):
    super().__init__(client)
    self.counter = deployment.config["initial_count"] if "initial_count" in deployment.config else 0
    self.topic_id_map = deployment.topic_id_map
    assert len(deployment.stream_groups) == 1
    assert len(deployment.stream_groups[0].inputs) == 0
    assert len(deployment.stream_groups[0].outputs) == 1
    self.output_stream_id = deployment.stream_groups[0].outputs[0].topic_id
  async def async_start(self, stop_signal: asyncio.Event):
    output_topic_id = self.topic_id_map[self.output_stream_id]
    async with self.client.provide_context([ output_topic_id ]):
      while not stop_signal.is_set():
        await asyncio.sleep(0.001)
        self.counter += 1
        await self.client.send_stream_data(output_topic_id, MessagePackData({ "count": self.counter }))

class CounterIncrementTask(Task):
  def __init__(self, client: Client, deployment: TaskDeployment):
    super().__init__(client)
    self.topic_id_map = deployment.topic_id_map
    assert len(deployment.stream_groups) == 1
    assert len(deployment.stream_groups[0].inputs) == 1
    assert len(deployment.stream_groups[0].outputs) == 1
    self.input_stream_id = deployment.stream_groups[0].inputs[0].topic_id
    self.output_stream_id = deployment.stream_groups[0].outputs[0].topic_id
  async def async_start(self, stop_signal: asyncio.Event):
    input_topic_id = self.topic_id_map[self.input_stream_id]
    output_topic_id = self.topic_id_map[self.output_stream_id]
    async with self.client.provide_context([ output_topic_id ]):
      async with self.client.get_topics_receiver([ input_topic_id ]) as receiver:
        while not stop_signal.is_set():
          await asyncio.sleep(0.001)
          topic_id, data, _ = await receiver.recv()
          assert topic_id == input_topic_id
          assert "count" in data.data
          count = data.data["count"]
          assert isinstance(count, int)
          await self.client.send_stream_data(output_topic_id, MessagePackData({ "count": count + 1 }))

class TestTaskFactoryWorker(TaskFactoryWorker):
  @property
  def task_format(self): return None
  @property
  def config_script(self): return ""

class CounterIncrementTaskFactory(TestTaskFactoryWorker):
  async def create_task(self, deployment: TaskDeployment) -> Task: return CounterIncrementTask(await self.create_client(), deployment)

class CounterEmitTaskFactory(TestTaskFactoryWorker):
  async def create_task(self, deployment: TaskDeployment) -> Task: return CounterEmitTask(await self.create_client(), deployment)

class TestTasks(unittest.IsolatedAsyncioTestCase):
  node: LocalNode
  worker: Worker

  stop_signal: asyncio.Event
  tasks: list[asyncio.Task]

  async def asyncSetUp(self):
    self.stop_signal = asyncio.Event()
    self.tasks = []
    self.node = LocalNode()

    dicovery_worker = DiscoveryWorker(0)
    await self.setup_worker(dicovery_worker)

    self.tasks.append(asyncio.create_task(self.node.async_start(self.stop_signal)))
    await asyncio.sleep(0.001)

  async def asyncTearDown(self):
    self.stop_signal.set()
    for task in self.tasks: await task

  async def setup_worker(self, worker: Worker):
    if hasattr(worker, "stop_timeout"): worker.stop_timeout = 0.1
    await worker.set_node_connection(await self.node.create_connection(raw=True))
    task = asyncio.create_task(worker.async_start(self.stop_signal))
    self.tasks.append(task)
    await worker.connected.wait()
    return task

  async def test_counter(self):
    managment_server = ASGITestServer()
    management_worker = TaskManagerWorker(0, managment_server)
    await self.setup_worker(management_worker)

    counter_emit_worker = CounterEmitTaskFactory(0)
    await self.setup_worker(counter_emit_worker)

    counter_increment_worker = CounterIncrementTaskFactory(0)
    await self.setup_worker(counter_increment_worker)

    client = Client(await self.node.create_connection())
    await client.request_address()

    deployments: list[TaskDeploymentBase] = [
      TaskDeploymentBase(
        task_factory_id=counter_emit_worker.id, 
        label="emit counter", 
        config={ "initial_count": 2 }, 
        stream_groups=[TaskStreamGroup(inputs=[],outputs=[TaskStream(label="count",topic_id="emit")])]
      ),
      TaskDeploymentBase(
        task_factory_id=counter_increment_worker.id,
        label="increment",
        config={},
        stream_groups=[TaskStreamGroup(inputs=[TaskStream(label="value in",topic_id="emit")], outputs=[TaskStream(label="value out",topic_id="increment")])]
      )
    ]

    await counter_emit_worker.wait_idle()
    await counter_increment_worker.wait_idle()
    web_client = await managment_server.wait_for_client()

    result = await web_client.post("/api/deployment", content=json.dumps([ deployment.dict() for deployment in deployments]))
    deployment: Deployment = Deployment.parse_obj(result.json())
    self.assertEqual(len(deployment.tasks), 2)
    self.assertEqual(deployment.tasks[0].label, "emit counter")
    self.assertEqual(deployment.tasks[1].label, "increment")

    result_topic_id = deployment.tasks[1].topic_id_map["increment"]
    async with client.get_topics_receiver([ result_topic_id ]) as receiver:
      await web_client.post(f"/api/deployment/{deployment.id}/start")
      topic_id, data, _ = await receiver.recv()
      last_value = data.data["count"]
      for _ in range(5):
        topic_id, data, _ = await receiver.recv()
        self.assertEqual(topic_id, result_topic_id)
        self.assertEqual(data.data["count"], last_value + 1)
        last_value = data.data["count"]


if __name__ == "__main__":
  unittest.main()