
from abc import abstractclassmethod, abstractmethod
import asyncio
from typing import Any, Optional, Union
from streamtasks.client import Client
from streamtasks.comm import Connection
from streamtasks.message.data import SerializableData
from streamtasks.streams import StreamSynchronizer, SynchronizedStream
from streamtasks.system.task import Task, TaskFactoryWorker
from streamtasks.system.types import DeploymentTask, DeploymentTaskScaffold, RPCTaskConnectRequest

class SynchronizedTaskInstance(Task):
  def __init__(self, client: Client, deployment: DeploymentTask, task: "SynchronizedTask"):
      super().__init__(client)
      self.deployment = deployment
      self.input_map: dict[str, Any] = {}
      self.input_paused_map = {}
      self.task = task
      self.update_lock = asyncio.Lock()
  
  async def start_task(self):
    try:
      output_topics = self.deployment.get_output_topic_ids()
      self.output_topic_map = { topic_id: self.deployment.topic_id_map[topic_id] for topic_id in output_topics }

      input_topic_map = ((self.deployment.topic_id_map[topic_id], topic_id) for topic_id in self.deployment.get_input_topic_ids())
      external_input_topics, internal_input_topics = zip(*input_topic_map)
      
      sync = StreamSynchronizer()
      input_streams = [ SynchronizedStream(sync, self.client.get_topics_receiver([ input_topic_id ])) for input_topic_id in external_input_topics ]
      input_recv_tasks = [ asyncio.create_task(self._run_receive_input(topic_id, stream)) for stream, topic_id in zip(input_streams, internal_input_topics)  ]
      
      await self.client.provide(self.output_topic_map.values())

    finally:
      for recv_task in input_recv_tasks: recv_task.cancel()
      await self.client.provide([])
  
  def _submit_update(self, timestamp: int):
    pass
  
  async def _run_update(self, timestamp: int, values: dict[str, Any]):
    async with self.update_lock:
      await self.task.update(timestamp, values)
    
  async def _run_receive_input(self, topic_id: str, stream: SynchronizedStream):
    async with stream:
      paused = False
      while True:
        with await stream.recv() as message:
          if message.data is not None:
            self.input_map[topic_id] = message.data.data
            self._submit_update(message.timestamp)
          if message.control is not None and message.control.paused != paused:
            paused = message.control.paused
            self.input_paused_map[topic_id] = paused

class SynchronizedTaskFactoryWorker(TaskFactoryWorker):
  def __init__(self, node_connection: Connection, task_component_cls: type["SynchronizedTask"]):
    super().__init__(node_connection)
    self.TaskComponent = task_component_cls
  
  @property
  def name(self): return self.TaskComponent.__name__
    
  async def create_task(self, deployment: DeploymentTask) -> Task: return self.TaskComponent(await self.create_client(), deployment)
  
  @property
  def task_template(self) -> DeploymentTask:
    scaffold = self.TaskComponent.task_scaffold()
    return DeploymentTask(
      task_factory_id=self.id,
      config={
        **scaffold.config,
        "label": self.TaskComponent.name(),
        "hostname": self.hostname,
      }
    )
  async def rpc_connect(self, req: RPCTaskConnectRequest) -> Optional[DeploymentTask]: return await self.TaskComponent.rpc_connect(req)
  async def rpc_on_editor(self, task: DeploymentTask) -> Union[DeploymentTask, list[dict[str, Any]]]: return await self.TaskComponent.rpc_on_editor(task)
  

class SynchronizedTask:
  def __init__(self):
    pass
  
  @classmethod
  def FactoryWorker(cls, node_connection: Connection): return SynchronizedTaskFactoryWorker(node_connection, cls)
  @classmethod
  def Task(cls, client: Client, deployment: DeploymentTask): pass
  
  @abstractclassmethod
  def name(cls) -> str: pass
  @abstractclassmethod
  def task_scaffold(cls) -> DeploymentTaskScaffold: pass
  @abstractclassmethod
  async def rpc_connect(cls, req: RPCTaskConnectRequest) -> Optional[DeploymentTask]: pass
  @classmethod
  async def rpc_on_editor(cls, task: DeploymentTask) -> Union[DeploymentTask, list[dict[str, Any]]]: return task, []
  
  async def request_update(self): pass
  async def emit(self, topic_id: str, data: SerializableData): pass
  async def set_subscribed(self, topic_id: str, subscribed: bool): pass
  async def get_subscribed(self) -> dict[str, bool]: pass
  async def set_output_paused(self, topic_id: str, paused: bool): pass
  async def get_outputs_paused(self) -> dict[str, bool]: pass
  async def get_inputs_paused(self) -> dict[str, bool]: pass
  
  async def setup(self): pass
  async def cleanup(self): pass
  @abstractmethod
  async def update(self, timestamp: int, values: dict[str, SerializableData]): pass
  