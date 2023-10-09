from dataclasses import dataclass
from streamtasks.client.topic import InTopicSynchronizer
from streamtasks.helpers import AsyncObservable
from streamtasks.net.types import TopicControlData
from streamtasks.system.task import Task, TaskFactoryWorker
from streamtasks.system.helpers import apply_task_stream_config, validate_stream_config
from streamtasks.system.types import RPCTaskConnectRequest, DeploymentTask, TaskStreamConfig, TaskStreamGroup, TaskInputStream, TaskOutputStream, DeploymentTask
from streamtasks.client import Client
from streamtasks.client.receiver import NoopReceiver
from streamtasks.message import NumberMessage
from streamtasks.streams import StreamSynchronizer, SynchronizedStream
import socket
import asyncio
from enum import Enum

class GateFailMode(Enum):
  CLOSED = "closed"
  OPEN = "open"

@dataclass
class GateConfig: 
  fail_mode: GateFailMode
  gate_topic: int
  in_topic: int
  out_topic: int

  @staticmethod
  def from_deployment_task(task: DeploymentTask):
    topic_id_map = task.topic_id_map

    return GateConfig(
      in_topic=topic_id_map[task.stream_groups[0].inputs[0].topic_id],
      gate_topic=topic_id_map[task.stream_groups[0].inputs[1].topic_id],
      out_topic=topic_id_map[task.stream_groups[0].outputs[0].topic_id],
      fail_mode=GateFailMode(task.config.get("fail_mode", GateFailMode.OPEN.value)),
    )

class GateState(AsyncObservable):
  def __init__(self) -> None:
    super().__init__()
    self.gate_paused: bool = False
    self.gate_errored: bool = False
    self.input_paused: bool = False
    self.gate_value: bool = True
  
  def get_open(self, fail_mode: GateFailMode):
    if self.input_paused or not self.gate_value: return False
    if fail_mode == GateFailMode.CLOSED and (self.gate_paused or self.gate_errored): return False
    return True
  def get_output_paused(self, fail_mode: GateFailMode): return not self.get_open(fail_mode)

class GateTask(Task):
  def __init__(self, client: Client, config: GateConfig):
    super().__init__(client)
    sync = InTopicSynchronizer()
    self.in_topic = self.client.sync_in_topic(config.in_topic, sync)
    self.gate_topic = self.client.sync_in_topic(config.gate_topic, sync)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.state = GateState()
    self.fail_mode = config.fail_mode

  async def start_task(self):
    tasks: list[asyncio.Task] = []
    try:
      async with self.in_topic, self.gate_topic, self.out_topic, self.in_topic.RegisterContext(), \
          self.gate_topic.RegisterContext(), self.out_topic.RegisterContext():

        tasks.append(asyncio.create_task(self.run_gate_recv()))
        tasks.append(asyncio.create_task(self.run_in_recv()))
        tasks.append(asyncio.create_task(self.run_out_pauser()))

        self.client.start()
        await asyncio.gather(*tasks)
    finally:
      for task in tasks: task.cancle()

  async def run_gate_recv(self):
    while True:
      data = await self.gate_topic.recv_data_control()
      if isinstance(data, TopicControlData):
        self.state.gate_paused = True
      else:
        try:
          msg = NumberMessage.model_validate(data.data)
          self.state.gate_value = msg.value > 0.5
          self.state.gate_errored = False
        except:
          self.state.gate_errored = True
  async def run_out_pauser(self):
    while True:
      await self.out_topic.set_paused(self.state.get_output_paused(self.fail_mode))
      await self.state.wait_change()
  async def run_in_recv(self):
    while True:
      data = await self.in_topic.recv_data_control()
      if isinstance(data, TopicControlData):
        self.state.input_paused = data.paused
      else: 
        if self.state.get_open(self.fail_mode):
          await self.out_topic.send(data)

class GateTaskFactoryWorker(TaskFactoryWorker):
  async def create_task(self, deployment: DeploymentTask): 
    return GateTask(await self.create_client(), GateConfig.from_deployment_task(deployment))
  
  async def rpc_connect(self, req: RPCTaskConnectRequest) -> DeploymentTask:
    if req.input_id == req.task.stream_groups[0].inputs[0].ref_id:
      if req.output_stream is None:
        req.task.stream_groups[0].inputs[0].topic_id = None
      else:
        apply_task_stream_config(req.task.stream_groups[0].inputs[0], req.output_stream)
        req.task.stream_groups[0].inputs[0].topic_id = req.output_stream.topic_id
        apply_task_stream_config(req.task.stream_groups[0].outputs[0], req.output_stream)
      
      return req.task
    elif req.input_id == req.task.stream_groups[0].inputs[1].ref_id:
      if req.output_stream is None: 
        req.task.stream_groups[0].inputs[1].topic_id = None
        return req.task
      else:
        validate_stream_config(req.output_stream, TaskStreamConfig(content_type="number"), "Gate input must be a number")
        req.task.stream_groups[0].inputs[1].topic_id = req.output_stream.topic_id
        return req.task

  @property
  def task_template(self): return DeploymentTask(
    id="gate",
    task_factory_id=self.id,
    config={
      "label": "Gate",
      "hostname": socket.gethostname(),
    },
    stream_groups=[
      TaskStreamGroup(
        inputs=[TaskInputStream(label="input"), TaskInputStream(label="gate", content_type="number")],    
        outputs=[TaskOutputStream(label="output")]      
      )
    ]
  )