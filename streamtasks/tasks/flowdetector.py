from streamtasks.system.task import Task, TaskFactoryWorker
from streamtasks.system.helpers import apply_task_stream_config
from streamtasks.system.types import RPCTaskConnectRequest, DeploymentTask, TaskStreamGroup, TaskInputStream, TaskOutputStream, DeploymentTask
from streamtasks.client import Client
from streamtasks.client.receiver import NoopReceiver
from streamtasks.message import NumberMessage, get_timestamp_from_message, SerializableData, MessagePackData
from streamtasks.helpers import TimeSynchronizer
import socket
import asyncio
from enum import Enum
from typing import Optional

class FlowDetectorFailMode(Enum):
  FAIL_CLOSED = "fail_closed"
  FAIL_OPEN = "fail_open"

class FlowDetectorTask(Task):
  def __init__(self, client: Client, deployment: DeploymentTask):
    super().__init__(client)    
    self.time_sync = TimeSynchronizer()
    self.setup_done = asyncio.Event()

    self.failing = False
    self.input_paused = False
    self.fail_mode = FlowDetectorFailMode(deployment.config.get("fail_mode", FlowDetectorFailMode.FAIL_OPEN.value))
    self.signal_delay = deployment.config["signal_delay"] if "signal_delay" in deployment.config else 1

    self.input_topic = client.create_subscription_tracker()
    self.output_topic = client.create_provide_tracker()
    self.signal_topic = client.create_provide_tracker()
    self.deployment = deployment

  async def start_task(self):
    try:
      topic_id_map = self.deployment.topic_id_map
      await self.input_topic.set_topic(topic_id_map[self.deployment.stream_groups[0].inputs[0].topic_id])
      await self.output_topic.set_topic(topic_id_map[self.deployment.stream_groups[0].outputs[0].topic_id])
      await self.signal_topic.set_topic(topic_id_map[self.deployment.stream_groups[0].outputs[1].topic_id])
      self.time_sync.reset()
      self.setup_done.set()

      return await asyncio.gather(
        self._process_messages(),
        self._process_subscription_status(),
        self._run_signal_loop()
      )
    finally:    
      self.time_sync.reset()
      self.input_paused = False
      self.failing = False
      self.fail_mode = FlowDetectorFailMode.FAIL_OPEN
      self.setup_done.clear()

      await self.input_topic.set_topic(None)
      await self.output_topic.set_topic(None)
      await self.signal_topic.set_topic(None)
  
  async def _run_signal_loop(self):
    while True:
      await asyncio.sleep(self.signal_delay)
      await self._on_state_change()

  async def _process_subscription_status(self):
    async with NoopReceiver(self.client):
      await self._on_state_change()
      while True:
        await self.output_topic.wait_subscribed_change()
        await self._on_state_change()

  async def _process_messages(self):
    async with self.client.get_topics_receiver([ self.input_topic ]) as receiver:
      while True:
        topic_id, data, control = await receiver.recv()
        if data is not None: await self._process_message(data)
        elif control is not None: self.input_paused = control.paused
        await self._on_state_change()

  async def _process_message(self, data: SerializableData):
    try: 
      self.time_sync.update(get_timestamp_from_message(data))
      self.failing = False
    except Exception as e: self.failing = True
    finally: await self.client.send_stream_data(self.output_topic.topic, data)

  async def _on_state_change(self, timestamp: Optional[int] = None):
    if timestamp is not None: self.time_sync.update(timestamp)
    await self.input_topic.set_subscribed(self.output_topic.is_subscribed)
    await self.output_topic.set_paused(self.input_paused)
    is_active = self.output_topic.is_subscribed and not self.input_paused and (not self.failing or self.fail_mode == FlowDetectorFailMode.FAIL_OPEN)
    message = NumberMessage(timestamp=self.time_sync.time if timestamp is None else timestamp, value=float(is_active))
    if self.signal_topic.topic is not None: 
      await self.client.send_stream_data(self.signal_topic.topic, MessagePackData(message.model_dump()))

class FlowDetectorTaskFactoryWorker(TaskFactoryWorker):
  async def create_task(self, deployment: DeploymentTask): return FlowDetectorTask(await self.create_client(), deployment)
  async def rpc_connect(self, req: RPCTaskConnectRequest) -> DeploymentTask: 
    if req.input_id != req.task.stream_groups[0].inputs[0].ref_id: raise Exception("Input stream id does not match task input stream id")
    if req.output_stream:
      req.task.stream_groups[0].inputs[0].topic_id = req.output_stream.topic_id
      apply_task_stream_config(req.task.stream_groups[0].inputs[0], req.output_stream)
      apply_task_stream_config(req.task.stream_groups[0].outputs[0], req.output_stream)
    else:
      req.task.stream_groups[0].inputs[0].topic_id = None
    return req.task
  @property
  def task_template(self): return DeploymentTask(
    task_factory_id=self.id,
    config= {
      "label": "Flow Detector",
      "hostname": socket.gethostname(),
    },
    stream_groups=[
      TaskStreamGroup(
        inputs=[TaskInputStream(label="input")],    
        outputs=[TaskOutputStream(label="output"), TaskOutputStream(label="signal", content_type="number")]      
      )
    ]
  )