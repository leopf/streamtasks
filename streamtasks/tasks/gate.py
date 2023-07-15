from streamtasks.system.task import Task
from streamtasks.system.workers import TaskFactoryWorker
from streamtasks.system.types import DeploymentTask, TaskStreamGroup, TaskInputStream, TaskOutputStream, DeploymentTask
from streamtasks.client import Client
from streamtasks.client.receiver import NoopReceiver
from streamtasks.message import NumberMessage, get_timestamp_from_message, SerializableData
from streamtasks.streams import StreamSynchronizer, SynchronizedStream
import socket
import asyncio
import logging
from enum import Enum

class GateFailMode(Enum):
  FAIL_CLOSED = "fail_closed"
  FAIL_OPEN = "fail_open"
  PASSIVE = "passive"

class GateTask(Task):
  def __init__(self, client: Client, deployment: DeploymentTask):
    super().__init__(client)
    self.deployment = deployment

    self.input_topic = client.create_subscription_tracker()
    self.gate_topic = client.create_subscription_tracker()
    self.output_topic = client.create_provide_tracker()

    stream_sync = StreamSynchronizer()
    self.input_stream = SynchronizedStream(stream_sync, client.get_topics_receiver([ self.input_topic ]))
    self.gate_stream = SynchronizedStream(stream_sync, client.get_topics_receiver([ self.gate_topic ]))

  async def start_task(self):
    try:
      await self._setup()
      return await asyncio.gather(
        self._process_gate_stream(),
        self._process_input_stream(),
        self._process_subscription_status(),
      )
    finally:    
      self.input_paused = False
      self.gate_open = self.default_gate_open
      await self.input_topic.set_topic(None)
      await self.gate_topic.set_topic(None)
      await self.output_topic.set_topic(None)
  
  async def _setup(self):
    topic_id_map = self.deployment.topic_id_map
    await self.input_topic.set_topic(topic_id_map[self.deployment.stream_groups[0].inputs[0].topic_id])
    await self.gate_topic.set_topic(topic_id_map[self.deployment.stream_groups[0].inputs[1].topic_id])
    await self.output_topic.set_topic(topic_id_map[self.deployment.stream_groups[0].outputs[0].topic_id])
    self.fail_mode = GateFailMode(self.deployment.config.get("fail_mode", GateFailMode.PASSIVE.value))
    self.gate_open = self.default_gate_open
    self.input_paused = False
  
  @property
  def default_gate_open(self): return False if self.fail_mode == GateFailMode.FAIL_CLOSED else True
  
  async def _process_subscription_status(self):
    async with NoopReceiver(self.client):
      while True:
        await self.output_topic.wait_subscribed_change()
        await self.on_state_change()

  async def _process_gate_stream(self):
    async with self.gate_stream:
      while True:
        with await self.gate_stream.recv() as message:
          if message.data is not None: 
            try:
              nmessage = NumberMessage.parse_obj(message.data.data)
              self.gate_open = float(nmessage.value) > 0.5
            except:
              if self.fail_mode != GateFailMode.PASSIVE: self.gate_open = self.default_gate_open
          if message.control is not None and message.control.paused and self.fail_mode != GateFailMode.PASSIVE: 
            self.gate_open = self.default_gate_open 
          await self.on_state_change()

  async def _process_input_stream(self):
    async with self.input_stream:
      while True:
        with await self.input_stream.recv() as message:
          if message.data is not None and self.gate_open: 
            await self.client.send_stream_data(self.output_topic.topic, message.data)
          if message.control is not None: self.input_paused = message.control.paused
          await self.on_state_change()
  
  async def on_state_change(self):
    await self.input_topic.set_subscribed(self.output_topic.is_subscribed)
    await self.output_topic.set_paused(self.input_paused or not self.gate_open)

class GateTaskFactoryWorker(TaskFactoryWorker):
  async def create_task(self, deployment: DeploymentTask): return GateTask(await self.create_client(), deployment)
  @property
  def config_script(self): return ""
  @property
  def task_template(self): return DeploymentTask(
    id="gate",
    task_factory_id=self.id,
    label="Gate",
    hostname=socket.gethostname(),
    stream_groups=[
      TaskStreamGroup(
        inputs=[TaskInputStream(label="input"), TaskInputStream(label="gate", content_type="number")],    
        outputs=[TaskOutputStream(label="output")]      
      )
    ]
  )