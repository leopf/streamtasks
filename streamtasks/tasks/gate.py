from streamtasks.system import Task, TaskFactoryWorker, TaskDeployment, TaskFormat, TaskStreamFormatGroup, TaskStreamFormat
from streamtasks.client import Client
from streamtasks.message.data import SerializableData
from streamtasks.message import NumberMessage
from streamtasks.streams.helpers import StreamValueTracker
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
    self.input_paused = False

  def can_update(self, deployment: TaskDeployment): return True
  async def update(self, deployment: TaskDeployment): await self._apply_deployment(deployment)
  async def async_start(self, stop_signal: asyncio.Event):
    await self._apply_deployment(self.deployment)
    async with self.client.get_topics_receiver([ self.input_topic_id, self.gate_topic_id ], subscribe=False) as receiver:
      while not stop_signal.is_set():
        topic_id, data, control = await receiver.recv()
        if data is not None:
          if topic_id == self.gate_topic.topic: await self._process_gate_message(data)
          elif topic_id == self.input_topic.topic: await self._process_input_message(data)
        elif control is not None:
          if topic_id == self.input_topic.topic: 
            self.input_paused = control.paused
            await self.update_stream_states()
          if topic_id == self.gate_topic.topic and control.paused and self.fail_mode != GateFailMode.PASSIVE: self.gate_value_tracker.set_stale()
          
    await self.input_topic.set_topic(None)
    await self.gate_topic.set_topic(None)
    await self.output_topic.set_topic(None)
  @property
  def default_gate_value(self): return 0 if self.fail_mode == GateFailMode.FAIL_CLOSED else 1
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
    if self.input_paused: await self.output_topic.pause()
    if not self.gate_value_tracker.has_value(lambda _, value: value >= 0.5, self.default_gate_value):
      await self.input_topic.unsubscribe()
      await self.output_topic.pause()
    else:
      await self.input_topic.subscribe()
      if not self.input_paused: await self.output_topic.resume()

  async def _apply_deployment(self, deployment: TaskDeployment):
    topic_id_map = deployment.topic_id_map
    await self.input_topic.set_topic(topic_id_map[deployment.stream_groups[0].inputs[0].topic_id])
    await self.gate_topic.set_topic(topic_id_map[deployment.stream_groups[0].inputs[1].topic_id])
    await self.output_topic.set_topic(topic_id_map[deployment.stream_groups[0].outputs[0].topic_id])
    self.fail_mode = GateFailMode(deployment.config.get("fail_mode", GateFailMode.PASSIVE.value))
    self.deployment = deployment

class GateTaskFactoryWorker(TaskFactoryWorker):
  async def create_task(self, deployment: TaskDeployment): return GateTask(await self.create_client(), deployment)
  @property
  def config_script(self): return ""
  @property
  def task_format(self): return TaskFormat(
    task_factory_id=self.id,
    label="Gate",
    hostname=socket.gethostname(),
    worker_id=self.worker_id,
    stream_groups=[
      TaskStreamFormatGroup(
        inputs=[TaskStreamFormat(label="input"), TaskStreamFormat(label="gate", content_type="number")],    
        outputs=[TaskStreamFormat(label="output")]      
      )
    ]
  )