from streamtasks.system.task import Task
from streamtasks.system.workers import TaskFactoryWorker
from streamtasks.system.types import TaskDeployment, TaskFormat, TaskStreamFormatGroup, TaskStreamFormat
from streamtasks.client import Client
from streamtasks.client.receiver import NoopReceiver
from streamtasks.message import NumberMessage, get_timestamp_from_message, SerializableData, MessagePackData
from streamtasks.streams import StreamValueTracker
from streamtasks.helpers import TimeSynchronizer
import socket
from pydantic import BaseModel
import asyncio
import logging
from enum import Enum
from typing import Optional

class FlowDetectorFailMode(Enum):
  FAIL_CLOSED = "fail_closed"
  FAIL_OPEN = "fail_open"

class FlowDetectorTask(Task):
  def __init__(self, client: Client, deployment: TaskDeployment):
    super().__init__(client)
    self.setup_done = asyncio.Event()
    
    self.time_sync = TimeSynchronizer()
    self.current_value = 0
    self.signal_delay = 1

    self.input_paused = False
    self.fail_mode = FlowDetectorFailMode.FAIL_OPEN

    self.input_topic = client.create_subscription_tracker()
    self.output_topic = client.create_provide_tracker()
    self.signal_topic = client.create_provide_tracker()
    self.deployment = deployment

  def can_update(self, deployment: TaskDeployment): return True
  async def update(self, deployment: TaskDeployment): await self._apply_deployment(deployment)
  async def start_task(self):
    try:
      return await asyncio.gather(
        self._setup(),
        self._process_messages(),
        self._process_subscription_status(),
        self._run_signal_loop()
      )
    finally:    
      self.time_sync.reset()
      self.current_value = 0
      self.input_paused = False
      self.fail_mode = FlowDetectorFailMode.FAIL_OPEN
      self.setup_done.clear()

      await self.input_topic.set_topic(None)
      await self.output_topic.set_topic(None)
      await self.signal_topic.set_topic(None)
  
  async def _setup(self):
    await self._apply_deployment(self.deployment)
    self.setup_done.set()
  
  async def _run_signal_loop(self):
    await self.setup_done.wait()
    while True:
      await asyncio.sleep(self.signal_delay)
      await self._update_value()

  async def _process_subscription_status(self):
    async def wait_subscribed():
      await self.output_topic.wait_subscribed()
      await self.output_topic.resume()
      await self.input_topic.subscribe()
      await self._update_value(1)

    async def wait_unsubscribed():
      await self.output_topic.wait_subscribed(False)
      await self.output_topic.pause()
      await self.input_topic.unsubscribe()
      await self._update_value(0)

    async with NoopReceiver(self.client):
      await self.setup_done.wait()
      await self._update_value(float(self.output_topic.is_subscribed)) # emit initial value
      while True:
        if self.output_topic.is_subscribed: await wait_unsubscribed()
        else: await wait_subscribed()

  async def _process_messages(self):
    async with self.client.get_topics_receiver([ self.input_topic ]) as receiver:
      await self.setup_done.wait()
      while True:
        topic_id, data, control = await receiver.recv()
        if data is not None: await self._process_message(data)
        elif control is not None:
          self.input_paused = control.paused
          await self.output_topic.set_paused(control.paused)
          await self._update_value()

  async def _process_message(self, data: SerializableData):
    try: 
      self.time_sync.set_time(get_timestamp_from_message(data))
    except Exception as e: 
      if self.fail_mode == FlowDetectorFailMode.FAIL_CLOSED: await self._update_value(0)
      if self.fail_mode == FlowDetectorFailMode.FAIL_OPEN: await self._update_value(1)
    finally: await self.client.send_stream_data(self.output_topic.topic, data)

  async def _update_value(self, value: Optional[float] = None):
    if value is not None: self.current_value = value
    if self.input_paused: message = NumberMessage(timestamp=self.time_sync.time, value=0)
    else: message = NumberMessage(timestamp=self.time_sync.time, value=self.current_value)
    if self.signal_topic.topic is not None: 
      await self.client.send_stream_data(self.signal_topic.topic, MessagePackData(message.dict()))

  async def _apply_deployment(self, deployment: TaskDeployment):
    topic_id_map = deployment.topic_id_map
    await self.input_topic.set_topic(topic_id_map[deployment.stream_groups[0].inputs[0].topic_id])
    await self.output_topic.set_topic(topic_id_map[deployment.stream_groups[0].outputs[0].topic_id])
    await self.signal_topic.set_topic(topic_id_map[deployment.stream_groups[0].outputs[1].topic_id])

    self.time_sync.reset()
    self.fail_mode = FlowDetectorFailMode(deployment.config.get("fail_mode", FlowDetectorFailMode.FAIL_OPEN.value))
    self.signal_delay = deployment.config["signal_delay"] if "signal_delay" in deployment.config else 1

    self.deployment = deployment

class FlowDetectorTaskFactoryWorker(TaskFactoryWorker):
  async def create_task(self, deployment: TaskDeployment): return FlowDetectorTask(await self.create_client(), deployment)
  @property
  def config_script(self): return ""
  @property
  def task_format(self): return TaskFormat(
    task_factory_id=self.id,
    label="Flow Detector",
    hostname=socket.gethostname(),
    stream_groups=[
      TaskStreamFormatGroup(
        inputs=[TaskStreamFormat(label="input")],    
        outputs=[TaskStreamFormat(label="output"), TaskStreamFormat(label="signal")]      
      )
    ]
  )