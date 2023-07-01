from streamtasks.task import Task, TaskFactoryWorker, TaskDeployment, TaskFormat, TaskStreamFormatGroup, TaskStreamFormat
from streamtasks.client import Client
from streamtasks.comm.serialization import SerializableData
import socket
from pydantic import BaseModel
import asyncio
import logging

class NumberMessage(BaseModel):
  value: float
  timestamp: int

def get_timestamp_from_message(data: SerializableData) -> int:
  content = data.data
  timestamp = None
  if isinstance(content, dict) and "timestamp" in content: timestamp = content["timestamp"]
  elif isinstance(content.timestamp, int): timestamp = content.timestamp
  else: raise Exception(f"could not get timestamp from message: {data}")
  if isinstance(timestamp, int): return timestamp
  if isinstance(timestamp, float): return int(timestamp)
  raise Exception(f"could not get timestamp from message: {data}")

class GateTask(Task):
  def __init__(self, client: Client, deployment: TaskDeployment):
    super().__init__(client)
    self.restart = asyncio.Event()
    self._set_deployment(deployment)
    self.stop_stream_after_timestamp = None

  def can_update(self, deployment: TaskDeployment): return True
  async def update(self, deployment: TaskDeployment):
    self._set_deployment(deployment)
    self.restart.set()

  async def async_start(self, stop_signal: asyncio.Event):
    while not stop_signal.is_set():
      await self._run(stop_signal)
      self.restart.clear()

  async def _run(self, stop_signal: asyncio.Event):
    async with self.client.provide([ self.output_topic_id ]):
      async with self.client.get_topics_receiver([ self.input_topic_id, self.gate_topic_id ]) as receiver:
        while not stop_signal.is_set() and not self.restart.is_set():
          topic_id, data, _ = await receiver.recv()
          if topic_id == self.gate_topic_id: await self._process_gate_message(data)
          elif topic_id == self.input_topic_id: await self._process_input_message(data)

  async def _process_input_message(self, data: SerializableData):
    try:
      timestamp = get_timestamp_from_message(data)
      if self.stop_stream_after_timestamp is not None and timestamp > self.stop_stream_after_timestamp: return
      await self.client.send_stream_data(self.output_topic_id, data)
    except Exception as e:
      logging.error(f"error processing input message: {e}")

  async def _process_gate_message(self, data: SerializableData):
    try:
      message: NumberMessage = NumberMessage.parse_obj(data.data)
      if message.value < 0.5: self.stop_stream_after_timestamp = message.timestamp
      else: self.stop_stream_after_timestamp = None
    except:
      if not self.fail_closed: self.stop_stream_after_timestamp = None

  async def _set_deployment(self, deployment: TaskDeployment):
    self.input_topic_id = deployment.topic_id_map[deployment.stream_groups[0].inputs[0].topic_id]
    self.gate_topic_id = deployment.topic_id_map[deployment.stream_groups[0].inputs[1].topic_id]
    self.output_topic_id = deployment.topic_id_map[deployment.stream_groups[0].outputs[0].topic_id]
    self.fail_closed = bool(deployment.config.get("fail_closed", False))

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