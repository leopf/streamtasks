from streamtasks.system.task import Task
from streamtasks.system.workers import TaskFactoryWorker
from streamtasks.system.types import TaskDeployment, TaskFormat, TaskStreamFormatGroup, TaskStreamFormat
from streamtasks.client import Client
from streamtasks.client.receiver import NoopReceiver
from streamtasks.message import NumberMessage, get_timestamp_from_message, SerializableData, MediaPacketData
from streamtasks.streams.helpers import StreamValueTracker
import socket
from pydantic import BaseModel
import asyncio
import logging
from enum import Enum

class FlowDetectorFailMode(Enum):
  FAIL_CLOSED = "fail_closed"
  FAIL_OPEN = "fail_open"
  PASSIVE = "passive"

class FlowDetectorTask(Task):
  def __init__(self, client: Client, deployment: TaskDeployment):
    super().__init__(client)
    self.message_receiver_ready = asyncio.Event()
    self.subscribe_receiver_ready = asyncio.Event()
    self.current_timestamp = 0
    self.current_value = 0
    self.input_paused = False
    self.fail_mode = FlowDetectorFailMode.PASSIVE

    self.input_topic = client.create_subscription_tracker()
    self.output_topic = client.create_provide_tracker()
    self.signal_topic = client.create_provide_tracker()
    self.deployment = deployment

  def can_update(self, deployment: TaskDeployment): return True
  async def update(self, deployment: TaskDeployment): await self._apply_deployment(deployment)
  async def start_task(self):
    try:
      return asyncio.gather(
        self._setup(),
        self._process_messages(),
        self._process_subscription_status(),
      )
    finally:    
      self.current_timestamp = 0
      self.current_value = 0
      self.input_paused = False
      self.fail_mode = FlowDetectorFailMode.PASSIVE
      await self.input_topic.set_topic(None)
      await self.output_topic.set_topic(None)
      await self.signal_topic.set_topic(None)
  
  async def _setup(self):
    await self.message_receiver_ready.wait()
    await self.subscribe_receiver_ready.wait()
    await self._apply_deployment(self.deployment)
  
  async def _process_subscription_status(self):
    async with NoopReceiver(self.client):
      self.subscribe_receiver_ready.set()
      while True:
        await self.output_topic.wait_subscribed(False)
        await self.output_topic.pause()
        await self._update_value(0)
        await self.input_topic.unsubscribe()
        await self.output_topic.wait_subscribed()
        await self.output_topic.resume()
        await self._update_value(float(self.input_paused))
        await self.input_topic.subscribe()

  async def _process_messages(self):
    async with self.client.get_topics_receiver([ self.input_topic ]) as receiver:
      self.message_receiver_ready.set()
      while True:
        topic_id, data, control = await receiver.recv()
        if data is not None:
          await self._process_message(data)
        elif control is not None:
          self.input_paused = control.paused
          await self.signal_topic.set_paused(control.paused)
          await self._update_value(float(control.paused))
  async def _process_message(self, data: SerializableData):
    try:
      timestamp = get_timestamp_from_message(data)
      self.current_timestamp = timestamp
    except: 
      if self.fail_mode == FlowDetectorFailMode.FAIL_CLOSED: await self._update_value(0)
      if self.fail_mode == FlowDetectorFailMode.FAIL_OPEN: await self._update_value(1)
    finally:
      if not self.output_topic.paused: await self.client.send_stream_data(self.output_topic.topic, data)

  async def _update_value(self, value: float):
    if value == self.current_value: return
    self.current_value = value
    self.current_timestamp += 1
    await self.client.send_stream_data(self.output_topic.topic, MediaPacketData(NumberMessage(timestamp=self.current_timestamp, value=value)))

  async def _apply_deployment(self, deployment: TaskDeployment):
    topic_id_map = deployment.topic_id_map
    await self.input_topic.set_topic(topic_id_map[deployment.stream_groups[0].inputs[0].topic_id])
    await self.output_topic.set_topic(topic_id_map[deployment.stream_groups[0].outputs[0].topic_id])
    await self.signal_topic.set_topic(topic_id_map[deployment.stream_groups[0].outputs[1].topic_id])
    self.fail_mode = FlowDetectorFailMode(deployment.config["fail_mode"])
    self.deployment = deployment

class FlowDetectorTaskFactoryWorker(TaskFactoryWorker):
  async def create_task(self, deployment: TaskDeployment): return FlowDetectorTask(await self.create_client(), deployment)
  @property
  def config_script(self): return ""
  @property
  def task_format(self): return TaskFormat(
    task_factory_id=self.id,
    label="Passivize",
    hostname=socket.gethostname(),
    stream_groups=[
      TaskStreamFormatGroup(
        inputs=[TaskStreamFormat(label="input")],    
        outputs=[TaskStreamFormat(label="output"), TaskStreamFormat(label="signal")]      
      )
    ]
  )