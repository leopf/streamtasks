from dataclasses import dataclass
from streamtasks.net.types import TopicControlData
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
  CLOSED = "closed"
  OPEN = "open"
  PASSIVE = "passive"

@dataclass
class FlowDetectorConfig:
  in_topic: int
  out_topic: int
  signal_topic: int
  fail_mode: FlowDetectorFailMode

  @staticmethod
  def from_deployment_task(task: DeploymentTask):
    topic_id_map = task.topic_id_map

    return FlowDetectorConfig(
      in_topic=topic_id_map[task.stream_groups[0].inputs[0].topic_id],
      out_topic=topic_id_map[task.stream_groups[0].outputs[0].topic_id],
      signal_topic=topic_id_map[task.stream_groups[0].outputs[1].topic_id],
      fail_mode=FlowDetectorFailMode(task.config.get("fail_mode", FlowDetectorFailMode.PASSIVE.value))
    )

class FlowDetectorTask(Task):
  def __init__(self, client: Client, config: FlowDetectorConfig):
    super().__init__(client)
    self.time_sync = TimeSynchronizer()
    self.in_topic = client.in_topic(config.in_topic)
    self.out_topic = client.out_topic(config.out_topic)
    self.signal_topic = client.out_topic(config.signal_topic)
    self.fail_mode = config.fail_mode
    self.current_signal = config.fail_mode == FlowDetectorFailMode.OPEN

  async def start_task(self):
    async with self.in_topic, self.out_topic, self.signal_topic, self.in_topic.RegisterContext(), \
        self.out_topic.RegisterContext(), self.signal_topic.RegisterContext():
      self.client.start()
      await self.set_output_paused(self.fail_mode == FlowDetectorFailMode.CLOSED)
      while True:
        data = await self.in_topic.recv_data_control()
        if isinstance(data, TopicControlData): await self.set_output_paused(data.paused)
        else: 
          try: 
            self.time_sync.update(get_timestamp_from_message(data))
            if self.fail_mode != FlowDetectorFailMode.PASSIVE and self.current_signal == self.out_topic.is_paused:
              await self.set_signal(not self.out_topic.is_paused)
          except: 
            if self.fail_mode == FlowDetectorFailMode.CLOSED: await self.set_signal(False)
            if self.fail_mode == FlowDetectorFailMode.OPEN: await self.set_signal(True)
          finally: await self.out_topic.send(data)
  async def set_signal(self, signal: bool):
    if signal != self.current_signal:
      await self.signal_topic.send(MessagePackData(NumberMessage(timestamp=self.time_sync.time, value=float(signal)).model_dump()))
      self.current_signal = signal
  async def set_output_paused(self, paused: bool):
    await self.out_topic.set_paused(paused)
    await self.set_signal(not paused)

class FlowDetectorTask2(Task):
  def __init__(self, client: Client, deployment: DeploymentTask):
    super().__init__(client)    
    self.time_sync = TimeSynchronizer()
    self.setup_done = asyncio.Event()

    self.failing = False
    self.input_paused = False
    self.fail_mode = FlowDetectorFailMode(deployment.config.get("fail_mode", FlowDetectorFailMode.OPEN.value))
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
      self.fail_mode = FlowDetectorFailMode.OPEN
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
    is_active = self.output_topic.is_subscribed and not self.input_paused and (not self.failing or self.fail_mode == FlowDetectorFailMode.OPEN)
    message = NumberMessage(timestamp=self.time_sync.time if timestamp is None else timestamp, value=float(is_active))
    if self.signal_topic.topic is not None: 
      await self.client.send_stream_data(self.signal_topic.topic, MessagePackData(message.model_dump()))

class FlowDetectorTaskFactoryWorker(TaskFactoryWorker):
  async def create_task(self, deployment: DeploymentTask): 
    return FlowDetectorTask(await self.create_client(), FlowDetectorConfig.from_deployment_task(deployment))
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