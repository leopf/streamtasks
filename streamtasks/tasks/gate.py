from streamtasks.system.task import Task
from streamtasks.system.workers import TaskFactoryWorker
from streamtasks.system.types import TaskDeployment, TaskFormat, TaskStreamFormatGroup, TaskStreamFormat
from streamtasks.client import Client
from streamtasks.client.receiver import NoopReceiver
from streamtasks.message import NumberMessage, get_timestamp_from_message, SerializableData
from streamtasks.streams import StreamValueTracker, StreamSynchronizer, SynchronizedStreamController
import socket
from pydantic import BaseModel
import asyncio
import logging
from enum import Enum

class GateFailMode(Enum):
  FAIL_CLOSED = "fail_closed"
  FAIL_OPEN = "fail_open"
  PASSIVE = "passive"

class GateTask(Task):
  def __init__(self, client: Client, deployment: TaskDeployment):
    super().__init__(client)
    self.input_topic = client.create_subscription_tracker()
    self.gate_topic = client.create_subscription_tracker()
    self.output_topic = client.create_provide_tracker()
    self.deployment = deployment
    self.gate_value_tracker = StreamValueTracker()
    self.fail_mode = GateFailMode.PASSIVE

    self.message_receiver_ready = asyncio.Event()
    self.subscribe_receiver_ready = asyncio.Event()
    self.setup_done = asyncio.Event()

    stream_sync = StreamSynchronizer()
    self.input_stream = SynchronizedStreamController(stream_sync)
    self.gate_stream = SynchronizedStreamController(stream_sync)

    self.input_paused = False

  async def start_task(self):
    try:
      return await asyncio.gather(
        self._setup(),
        self._process_messages(),
        self._process_subscription_status(),
      )
    finally:    
      self.input_paused = False
      self.gate_value_tracker.reset()
      await self.input_topic.set_topic(None)
      await self.gate_topic.set_topic(None)
      await self.output_topic.set_topic(None)
  
  async def _setup(self):
    await self.message_receiver_ready.wait()
    await self.subscribe_receiver_ready.wait()

    topic_id_map = self.deployment.topic_id_map
    await self.input_topic.set_topic(topic_id_map[self.deployment.stream_groups[0].inputs[0].topic_id])
    await self.gate_topic.set_topic(topic_id_map[self.deployment.stream_groups[0].inputs[1].topic_id])
    await self.output_topic.set_topic(topic_id_map[self.deployment.stream_groups[0].outputs[0].topic_id])
    self.fail_mode = GateFailMode(self.deployment.config.get("fail_mode", GateFailMode.PASSIVE.value))

    self.setup_done.set()
  
  @property
  def default_gate_value(self): return 0 if self.fail_mode == GateFailMode.FAIL_CLOSED else 1
  
  async def _process_subscription_status(self):
    async with NoopReceiver(self.client):
      self.subscribe_receiver_ready.set()
      await self.setup_done.wait()
      while True:
        await self.output_topic.wait_subscribed(False)
        await self.output_topic.pause()
        await self.input_topic.unsubscribe()
        await self.gate_topic.unsubscribe()
        await self.output_topic.wait_subscribed()
        await self.update_stream_states()

  async def _process_messages(self):
    async with self.client.get_topics_receiver([ self.input_topic, self.gate_topic ]) as receiver:
      self.message_receiver_ready.set()
      await self.setup_done.wait()
      while True:
        topic_id, data, control = await receiver.recv()
        if data is not None:
          if topic_id == self.gate_topic.topic: await self._process_gate_message(data)
          elif topic_id == self.input_topic.topic: await self._process_input_message(data)
        elif control is not None:
          if topic_id == self.input_topic.topic: 
            self.input_paused = control.paused
            await self.update_stream_states()
          if topic_id == self.gate_topic.topic and self.fail_mode != GateFailMode.PASSIVE: 
            if control.paused: self.gate_value_tracker.set_stale()
  
  async def _process_input_message(self, data: SerializableData):
    try:
      timestamp = get_timestamp_from_message(data)
      gate_value = self.gate_value_tracker.pop(timestamp, self.default_gate_value)
      if gate_value > 0.5: await self.client.send_stream_data(self.output_topic.topic, data)
      await self.update_stream_states()
    except Exception as e:
      logging.error(f"error processing input message: {e}")
  
  async def _process_gate_message(self, data: SerializableData):
    try:
      message: NumberMessage = NumberMessage.parse_obj(data.data)
      self.gate_value_tracker.add(message.timestamp, message.value)
    except: 
      if self.fail_mode != GateFailMode.PASSIVE: self.gate_value_tracker.set_stale()
    finally: await self.update_stream_states()
  
  async def update_stream_states(self):
    await self.gate_topic.subscribe()
    if self.input_paused: await self.output_topic.pause()
    if not self.gate_value_tracker.has_value(lambda _, value: value >= 0.5, self.default_gate_value):
      await self.input_topic.unsubscribe()
      await self.output_topic.pause()
    else:
      await self.input_topic.subscribe()
      if not self.input_paused: await self.output_topic.resume()

class GateTaskFactoryWorker(TaskFactoryWorker):
  async def create_task(self, deployment: TaskDeployment): return GateTask(await self.create_client(), deployment)
  @property
  def config_script(self): return ""
  @property
  def task_format(self): return TaskFormat(
    task_factory_id=self.id,
    label="Gate",
    hostname=socket.gethostname(),
    stream_groups=[
      TaskStreamFormatGroup(
        inputs=[TaskStreamFormat(label="input"), TaskStreamFormat(label="gate", content_type="number")],    
        outputs=[TaskStreamFormat(label="output")]      
      )
    ]
  )