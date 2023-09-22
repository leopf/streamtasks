
from abc import abstractclassmethod, abstractmethod
import asyncio
from functools import cached_property
from typing import Any, Optional, Union
from streamtasks.client import Client
from streamtasks.comm import Link
from streamtasks.comm.types import TopicControlData
from streamtasks.helpers import TimeSynchronizer
from streamtasks.message.data import SerializableData
from streamtasks.message.helpers import get_timestamp_from_message
from streamtasks.streams import StreamSynchronizer, SynchronizedStream
from streamtasks.system.task import Task, TaskFactoryWorker
from streamtasks.system.types import DeploymentTask, DeploymentTaskScaffold, RPCTaskConnectRequest, RPCUIEventRequest, RPCUIEventResponse

class SynchronizedTaskFactoryWorker(TaskFactoryWorker):
  def __init__(self, node_link: Link, task_component_cls: type["SynchronizedTask"]):
    super().__init__(node_link)
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
  async def rpc_ui_event(self, req: RPCUIEventRequest) -> RPCUIEventResponse: return await self.TaskComponent.rpc_ui_event(req)

class SynchronizedTask(Task):
  def __init__(self, client: Client, deployment: DeploymentTask):
      super().__init__(client)
      self.deployment = deployment
      self._input_map: dict[str, Any] = {}
      self._time_sync = TimeSynchronizer()
      self._current_timestamp = 0
      
      self._int_ext_topic_map = self.deployment.topic_id_map
      self._ext_int_topic_map = { topic_id: topic for topic, topic_id in self._int_ext_topic_map.items() }
      
      self._input_paused_map = {}
      self._input_subscribed_map = {}
      self._output_paused_map = {}
      self._update_lock = asyncio.Lock()
  
  @classmethod
  def FactoryWorker(cls, node_connection: Link): return SynchronizedTaskFactoryWorker(node_connection, cls)
  
  @abstractclassmethod
  def name(cls) -> str: pass
  @abstractclassmethod
  def task_scaffold(cls) -> DeploymentTaskScaffold: pass
  @abstractclassmethod
  async def rpc_connect(cls, req: RPCTaskConnectRequest) -> Optional[DeploymentTask]: pass
  @classmethod
  async def rpc_ui_event(cls, req: RPCUIEventRequest) -> RPCUIEventResponse: return RPCUIEventResponse(task=req.task)
  
  async def setup(self): pass
  async def cleanup(self): pass
  @abstractmethod
  async def on_changed(self, timestamp: int, **kwargs: Any): pass
  
  @property
  def topic_label_map(self) -> dict[str, str]: return {}
  
  async def start_task(self):
    try:
      input_topic_map = { self._int_ext_topic_map[topic_id]: topic_id for topic_id in self.deployment.get_input_topic_ids() }
      external_input_topics, internal_input_topics = zip(*input_topic_map.items())
      
      sync = StreamSynchronizer()
      input_streams = [ SynchronizedStream(sync, self.client.get_topics_receiver([ input_topic_id ], subscribe=False)) for input_topic_id in external_input_topics ]
      
      await self.client.subscribe(external_input_topics)
      self._input_subscribed_map = { topic_id: True for topic_id in internal_input_topics }
      
      await self.client.provide(self._int_ext_topic_map[topic_id] for topic_id in self.deployment.get_output_topic_ids())
      await self.setup()
      
      input_recv_tasks = [ asyncio.create_task(self._run_receive_input(topic_id, stream)) for stream, topic_id in zip(input_streams, internal_input_topics)  ]
      
      await asyncio.Future() # wait forever
    finally:
      for recv_task in input_recv_tasks: recv_task.cancel()
      await self.client.provide([])
      await self.cleanup()
  
  def request_changed(self): self._submit_changed()
  
  async def emit(self, topic_label: str, data: SerializableData):
    if not self._update_lock.locked():
      raise Exception("emit() can only be called from within update(). This is to prevent synchronization errors.")
    timestamp = get_timestamp_from_message(data)
    if timestamp > self._current_timestamp: raise Exception("emit() called with timestamp in the future")
    topic_id = self._topic_label_to_id(topic_label)
    await self.client.send_stream_data(self._int_ext_topic_map[topic_id], data)
      
  async def set_subscribed(self, topic_label: str, subscribed: bool):
    topic_id = self._topic_label_to_id(topic_label)
    if subscribed == self._input_subscribed_map[topic_id]: return
    if subscribed: await self.client.subscribe([ self._int_ext_topic_map[topic_id] ])
    else: await self.client.unsubscribe([ self._int_ext_topic_map[topic_id] ])
    self._input_subscribed_map[topic_id] = subscribed
    
  async def get_subscribed(self) -> dict[str, bool]: return self._input_subscribed_map
  async def set_output_paused(self, topic_label: str, paused: bool):
    topic_id = self._topic_label_to_id(topic_label)
    if paused == self._output_paused_map[topic_id]: return
    await self.client.send_stream_control(self._int_ext_topic_map[topic_id], TopicControlData(paused=paused))
    self._output_paused_map[topic_id] = paused
    
  async def get_outputs_paused(self) -> dict[str, bool]: return { self._topic_id_to_label(topic_id): paused for topic_id, paused in self._output_paused_map.items() }
  async def get_inputs_paused(self) -> dict[str, bool]: return { self._topic_id_to_label(topic_id): paused for topic_id, paused in self._input_paused_map.items() }
  
  @property
  def _reversed_topic_label_map(self) -> dict[str, str]: return { topic_id: topic_label for topic_label, topic_id in self.topic_label_map.items() }
  
  def _submit_changed(self, timestamp: Optional[int] = None):
    if timestamp is not None:
      self._time_sync.update(timestamp)
    else:
      timestamp = self._time_sync.time
    asyncio.create_task(self._run_changed(timestamp, { **self._input_map }))
  
  async def _run_changed(self, timestamp: int, values: dict[str, Any]):
    async with self._update_lock:
      self._current_timestamp = timestamp
      await self.on_changed(timestamp, **values)
    
  async def _run_receive_input(self, topic_id: str, stream: SynchronizedStream):
    async with stream:
      paused = False
      while True:
        with await stream.recv() as message:
          if message.data is not None:
            self._input_map[topic_id] = message.data.data
            self._submit_changed(message.timestamp)
          if message.control is not None and message.control.paused != paused:
            paused = message.control.paused
            self._input_paused_map[topic_id] = paused
  
  def _topic_label_to_id(self, topic_label: str) -> str:
    if topic_label in self.topic_label_map: return self.topic_label_map[topic_label]
    return topic_label
  def _topic_id_to_label(self, topic_id: str) -> str:
    if topic_id in self._reversed_topic_label_map: return self._reversed_topic_label_map[topic_id]
    return topic_id