from streamtasks.system.task import Task, TaskFactoryWorker
from streamtasks.system.helpers import apply_task_stream_config
from streamtasks.system.types import RPCTaskConnectRequest, DeploymentTask, TaskStreamGroup, TaskInputStream, TaskOutputStream, DeploymentTask
from streamtasks.client import Client
from streamtasks.client.receiver import NoopReceiver
import socket
import asyncio

class PassivizeTask(Task):
  def __init__(self, client: Client, deployment: DeploymentTask):
    super().__init__(client)
    self.message_receiver_ready = asyncio.Event()
    self.subscribe_receiver_ready = asyncio.Event()

    self.input_topic = client.create_subscription_tracker()
    self.active_output_topic = client.create_provide_tracker()
    self.passive_output_topic = client.create_provide_tracker()
    self.deployment = deployment

  def can_update(self, deployment: DeploymentTask): return True
  async def update(self, deployment: DeploymentTask): await self._apply_deployment(deployment)
  async def start_task(self):
    try:
      return await asyncio.gather(
        self._setup(),
        self._process_messages(),
        self._process_subscription_status(),
      )
    finally:    
      await self.input_topic.set_topic(None)
      await self.active_output_topic.set_topic(None)
      await self.passive_output_topic.set_topic(None)
  
  async def _setup(self):
    await self.message_receiver_ready.wait()
    await self.subscribe_receiver_ready.wait()
    await self._apply_deployment(self.deployment)
  
  async def _process_subscription_status(self):
    async with NoopReceiver(self.client):
      self.subscribe_receiver_ready.set()
      while True:
        await self.active_output_topic.wait_subscribed(False)
        await self.active_output_topic.pause()
        await self.passive_output_topic.pause()
        await self.input_topic.unsubscribe()
        await self.active_output_topic.wait_subscribed()
        await self.active_output_topic.resume()
        await self.passive_output_topic.resume()
        await self.input_topic.subscribe()

  async def _process_messages(self):
    async with self.client.get_topics_receiver([ self.input_topic ]) as receiver:
      self.message_receiver_ready.set()
      while True:
        topic_id, data, control = await receiver.recv()
        if data is not None and not self.passive_output_topic.paused and not self.active_output_topic.paused:
          await self.client.send_stream_data(self.active_output_topic.topic, data)
          if self.passive_output_topic.is_subscribed: await self.client.send_stream_data(self.passive_output_topic.topic, data)
        elif control is not None:
          await self.passive_output_topic.set_paused(control.paused)
          await self.active_output_topic.set_paused(control.paused)

  async def _apply_deployment(self, deployment: DeploymentTask):
    topic_id_map = deployment.topic_id_map
    await self.input_topic.set_topic(topic_id_map[deployment.stream_groups[0].inputs[0].topic_id])
    await self.active_output_topic.set_topic(topic_id_map[deployment.stream_groups[0].outputs[0].topic_id])
    await self.passive_output_topic.set_topic(topic_id_map[deployment.stream_groups[0].outputs[1].topic_id])
    self.deployment = deployment

class PassivizeTaskFactoryWorker(TaskFactoryWorker):
  async def create_task(self, deployment: DeploymentTask): return PassivizeTask(await self.create_client(), deployment)
  async def rpc_connect(self, req: RPCTaskConnectRequest) -> DeploymentTask: 
    if req.input_id != req.task.stream_groups[0].inputs[0].ref_id: raise Exception("Input stream id does not match task input stream id")
    if req.output_stream:
      req.task.stream_groups[0].inputs[0].topic_id = req.output_stream.topic_id
      apply_task_stream_config(req.task.stream_groups[0].inputs[0], req.output_stream)
      apply_task_stream_config(req.task.stream_groups[0].outputs[0], req.output_stream)
      apply_task_stream_config(req.task.stream_groups[0].outputs[1], req.output_stream)
    else:
      req.task.stream_groups[0].inputs[0].topic_id = None
    return req.task
  @property
  def task_template(self): return DeploymentTask(
    task_factory_id=self.id,
    config={
      "label": "Passivize",
      "hostname": socket.gethostname(),
    },
    stream_groups=[
      TaskStreamGroup(
        inputs=[TaskInputStream(label="input")],    
        outputs=[TaskOutputStream(label="active output"), TaskOutputStream(label="passive output")]      
      )
    ]
  )