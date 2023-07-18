from streamtasks.helpers import get_timestamp_ms
from streamtasks.message.data import MessagePackData
from streamtasks.message.structures import NumberMessage
from streamtasks.system.task import Task
from streamtasks.system.workers import TaskFactoryWorker
from streamtasks.system.types import RPCTaskConnectRequest, DeploymentTask, TaskStreamGroup, TaskOutputStream, DeploymentTask
from streamtasks.client import Client
import socket
import asyncio

class CounterTask(Task):
  def __init__(self, client: Client, deployment: DeploymentTask):
    super().__init__(client)
    self.output_topic = client.create_provide_tracker()
    self.deployment = deployment
    self.count = deployment.config.get("initial_count", 0)
    self.delay = deployment.config.get("delay", 1)

  async def start_task(self):
    try:
      while True:
        await self.client.send_stream_data(self.output_topic.topic, MessagePackData(NumberMessage(value=self.count, timestamp=get_timestamp_ms())))
        await asyncio.sleep(self.delay)
        self.count += 1
    finally:
      self.count = self.deployment.config.get("initial_count", 0)
      await self.output_topic.set_topic(None)
  
class CounterTaskFactoryWorker(TaskFactoryWorker):
  async def create_task(self, deployment: DeploymentTask): return CounterTask(await self.create_client(), deployment)
  async def rpc_connect(self, req: RPCTaskConnectRequest) -> DeploymentTask: pass
  @property
  def task_template(self): return DeploymentTask(
    task_factory_id=self.id,
    config={
      "label": "Counter",
      "hostname": socket.gethostname(),
    },
    stream_groups=[
      TaskStreamGroup(
        inputs=[],    
        outputs=[TaskOutputStream(label="output", content_type="number")]      
      )
    ]
  )