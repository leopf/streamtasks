from streamtasks.system.task import Task
from streamtasks.system.workers import TaskFactoryWorker
from streamtasks.system.types import DeploymentTaskFull, TaskStreamGroup, TaskInputStream, TaskOutputStream, DeploymentTask
from streamtasks.client import Client
from streamtasks.client.receiver import NoopReceiver
from streamtasks.message import NumberMessage, get_timestamp_from_message, SerializableData
import socket
from pydantic import BaseModel
import asyncio
import logging
from enum import Enum

class PassivizeTask(Task):
  def __init__(self, client: Client, deployment: DeploymentTaskFull):
    super().__init__(client)
    self.message_receiver_ready = asyncio.Event()
    self.subscribe_receiver_ready = asyncio.Event()

    self.input_topic = client.create_subscription_tracker()
    self.active_output_topic = client.create_provide_tracker()
    self.passive_output_topic = client.create_provide_tracker()
    self.deployment = deployment

  def can_update(self, deployment: DeploymentTaskFull): return True
  async def update(self, deployment: DeploymentTaskFull): await self._apply_deployment(deployment)
  async def start_task(self):
    try:
      return await asyncio.gather(
        self._setup(),
        self._process_messages(),
        self._process_subscription_status(),
      )
    finally:    
      await self.input_topic.set_topic(None)
      await self.active_output_topic.set_topic(None)
      await self.passive_output_topic.set_topic(None)
  
  async def _setup(self):
    await self.message_receiver_ready.wait()
    await self.subscribe_receiver_ready.wait()
    await self._apply_deployment(self.deployment)
  
  async def _process_subscription_status(self):
    async with NoopReceiver(self.client):
      self.subscribe_receiver_ready.set()
      while True:
        await self.active_output_topic.wait_subscribed(False)
        await self.active_output_topic.pause()
        await self.passive_output_topic.pause()
        await self.input_topic.unsubscribe()
        await self.active_output_topic.wait_subscribed()
        await self.active_output_topic.resume()
        await self.passive_output_topic.resume()
        await self.input_topic.subscribe()

  async def _process_messages(self):
    async with self.client.get_topics_receiver([ self.input_topic ]) as receiver:
      self.message_receiver_ready.set()
      while True:
        topic_id, data, control = await receiver.recv()
        if data is not None and not self.passive_output_topic.paused and not self.active_output_topic.paused:
          await self.client.send_stream_data(self.active_output_topic.topic, data)
          if self.passive_output_topic.is_subscribed: await self.client.send_stream_data(self.passive_output_topic.topic, data)
        elif control is not None:
          await self.passive_output_topic.set_paused(control.paused)
          await self.active_output_topic.set_paused(control.paused)

  async def _apply_deployment(self, deployment: DeploymentTaskFull):
    topic_id_map = deployment.topic_id_map
    await self.input_topic.set_topic(topic_id_map[deployment.stream_groups[0].inputs[0].topic_id])
    await self.active_output_topic.set_topic(topic_id_map[deployment.stream_groups[0].outputs[0].topic_id])
    await self.passive_output_topic.set_topic(topic_id_map[deployment.stream_groups[0].outputs[1].topic_id])
    self.deployment = deployment

class PassivizeTaskFactoryWorker(TaskFactoryWorker):
  async def create_task(self, deployment: DeploymentTaskFull): return PassivizeTask(await self.create_client(), deployment)
  @property
  def config_script(self): return ""
  @property
  def task_format(self): return DeploymentTask(
    id="passivize",
    task_factory_id=self.id,
    label="Passivize",
    hostname=socket.gethostname(),
    stream_groups=[
      TaskStreamGroup(
        inputs=[TaskInputStream(ref_id="in1", label="input")],    
        outputs=[TaskOutputStream(topic_id="out1", label="active output"), TaskOutputStream(topic_id="out2", label="passive output")]      
      )
    ]
  )