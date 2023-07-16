from __future__ import annotations
import unittest
from streamtasks.worker import Worker
from streamtasks.node import *
from streamtasks.message.data import MessagePackData
from streamtasks.client import *
from streamtasks.system.task import Task
from streamtasks.system.workers import TaskFactoryWorker, TaskManagerWorker
from streamtasks.system.types import *
from streamtasks.system.helpers import ASGITestServer
from streamtasks.system.discovery import DiscoveryWorker
import asyncio
from pydantic import parse_obj_as
import json

class CounterEmitTask(Task):
  def __init__(self, client: Client, deployment: DeploymentTask):
    super().__init__(client)
    self.counter = deployment.config["initial_count"] if "initial_count" in deployment.config else 0
    self.topic_id_map = deployment.topic_id_map
    assert len(deployment.stream_groups) == 1
    assert len(deployment.stream_groups[0].inputs) == 0
    assert len(deployment.stream_groups[0].outputs) == 1
    self.output_stream_id = deployment.stream_groups[0].outputs[0].topic_id
  async def start_task(self):
    output_topic_id = self.topic_id_map[self.output_stream_id]
    async with self.client.provide_context([ output_topic_id ]):
      while True:
        await asyncio.sleep(0.001)
        self.counter += 1
        await self.client.send_stream_data(output_topic_id, MessagePackData({ "count": self.counter }))

class CounterMultipyTask(Task):
  def __init__(self, client: Client, deployment: DeploymentTask):
    super().__init__(client)
    self.multiplier = deployment.config["multiplier"] if "multiplier" in deployment.config else 2
    self.topic_id_map = deployment.topic_id_map
    assert len(deployment.stream_groups) == 1
    assert len(deployment.stream_groups[0].inputs) == 1
    assert len(deployment.stream_groups[0].outputs) == 1
    self.input_stream_id = deployment.stream_groups[0].inputs[0].topic_id
    self.output_stream_id = deployment.stream_groups[0].outputs[0].topic_id
  async def start_task(self):
    input_topic_id = self.topic_id_map[self.input_stream_id]
    output_topic_id = self.topic_id_map[self.output_stream_id]
    async with self.client.provide_context([ output_topic_id ]):
      async with self.client.get_topics_receiver([ input_topic_id ]) as receiver:
        while True:
          topic_id, data, _ = await receiver.recv()
          assert topic_id == input_topic_id
          assert "count" in data.data
          count = data.data["count"]
          assert isinstance(count, int)
          await self.client.send_stream_data(output_topic_id, MessagePackData({ "count": count * self.multiplier }))

class TestTaskFactoryWorker(TaskFactoryWorker):
  @property
  def config_script(self): return ""

class CounterIncrementTaskFactory(TestTaskFactoryWorker):
  async def create_task(self, deployment: DeploymentTask) -> Task: return CounterMultipyTask(await self.create_client(), deployment)
  @property
  def task_template(self): return DeploymentTask(
    id="counter_increment",
    task_factory_id=self.id,
    label="increment",
    config={ },
    stream_groups=[TaskStreamGroup(inputs=[TaskInputStream(ref_id="in1", label="value in",topic_id="emit")], outputs=[TaskOutputStream(label="value out",topic_id="increment")])]
  )


class CounterEmitTaskFactory(TestTaskFactoryWorker):
  async def create_task(self, deployment: DeploymentTask) -> Task: return CounterEmitTask(await self.create_client(), deployment)
  
  @property
  def task_template(self): return DeploymentTask(
    id="counter_emit",
    task_factory_id=self.id, 
    label="counter emit", 
    config={}, 
    stream_groups=[TaskStreamGroup(inputs=[],outputs=[TaskOutputStream(label="count",topic_id="emit")])]
  )

class TestDeployment(unittest.IsolatedAsyncioTestCase):
  node: LocalNode
  worker: Worker

  tasks: list[asyncio.Task]

  async def asyncSetUp(self):
    self.tasks = []
    self.node = LocalNode()

    dicovery_worker = DiscoveryWorker(await self.node.create_connection(raw=True))
    await self.setup_worker(dicovery_worker)

    self.tasks.append(asyncio.create_task(self.node.start()))

    await asyncio.sleep(0.001)

    self.managment_server = ASGITestServer()
    self.management_worker = TaskManagerWorker(await self.node.create_connection(raw=True), self.managment_server)
    await self.setup_worker(self.management_worker)

    self.counter_emit_worker = CounterEmitTaskFactory(await self.node.create_connection(raw=True))
    await self.setup_worker(self.counter_emit_worker)

    self.counter_increment_worker = CounterIncrementTaskFactory(await self.node.create_connection(raw=True))
    await self.setup_worker(self.counter_increment_worker)

  async def asyncTearDown(self):
    for task in self.tasks:
      if task.done(): await task
      else: task.cancel()

  async def setup_worker(self, worker: Worker):
    if hasattr(worker, "stop_timeout"): worker.stop_timeout = 0.1
    task = asyncio.create_task(worker.start())
    self.tasks.append(task)
    await worker.connected.wait()
    return task

  async def test_task_templates_list(self):
    async with asyncio.timeout(1):
      await self.counter_emit_worker.wait_idle()
      await self.counter_increment_worker.wait_idle()
      web_client = await self.managment_server.wait_for_client()

      result = await web_client.get("/api/task-templates")
      tasks: list[DeploymentTask] = parse_obj_as(list[DeploymentTask], result.json())
      ids = [ task.task_factory_id for task in tasks ]
      self.assertEqual(len(tasks), 2)
      self.assertIn(self.counter_emit_worker.id, ids)
      self.assertIn(self.counter_increment_worker.id, ids)

  async def test_counter_deploy(self):
    async with asyncio.timeout(1):
      client = Client(await self.node.create_connection())
      await client.request_address()

      multiplier = 42

      deployments: list[DeploymentTask] = [
        DeploymentTask(
          task_factory_id=self.counter_emit_worker.id, 
          label="emit counter", 
          config={ "initial_count": 2 }, 
          stream_groups=[TaskStreamGroup(inputs=[],outputs=[TaskOutputStream(label="count",topic_id="emit")])]
        ),
        DeploymentTask(
          task_factory_id=self.counter_increment_worker.id,
          label="increment",
          config={ "multiplier": multiplier },
          stream_groups=[TaskStreamGroup(inputs=[TaskInputStream(label="value in",topic_id="emit")], outputs=[TaskOutputStream(label="value out",topic_id="increment")])]
        )
      ]

      await self.counter_emit_worker.wait_idle()
      await self.counter_increment_worker.wait_idle()
      web_client = await self.managment_server.wait_for_client()

      result = await web_client.post("/api/deployment", content=json.dumps([ deployment.dict() for deployment in deployments]))
      deployment: Deployment = Deployment.parse_obj(result.json())
      self.assertEqual(len(deployment.tasks), 2)
      self.assertEqual(deployment.tasks[0].label, "emit counter")
      self.assertEqual(deployment.tasks[1].label, "increment")

      await web_client.post(f"/api/deployment/{deployment.id}/start")
      result = await web_client.get(f"/api/deployment/{deployment.id}/started")
      deployment: Deployment = Deployment.parse_obj(result.json())
      result_topic_id = deployment.tasks[1].topic_id_map["increment"]
      async with client.get_topics_receiver([ result_topic_id ]) as receiver:
        topic_id, data, _ = await receiver.recv()
        last_value = data.data["count"]
        for _ in range(5):
          topic_id, data, _ = await receiver.recv()
          self.assertEqual(topic_id, result_topic_id)
          self.assertEqual(data.data["count"], last_value + multiplier)
          last_value = data.data["count"]


if __name__ == "__main__":
  unittest.main()