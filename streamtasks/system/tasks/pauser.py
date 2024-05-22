import asyncio
from typing import Any
from pydantic import BaseModel
from streamtasks.net.message.types import TopicControlData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.utils import AsyncTrigger
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class PauserConfigBase(BaseModel):
  after_duration: float = 1

class PauserConfig(PauserConfigBase):
  out_topic: int
  in_topic: int

class PauserTask(Task):
  def __init__(self, client: Client, config: PauserConfig):
    super().__init__(client)
    self.conifg = config
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.message_trigger = AsyncTrigger()

  async def run(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      await asyncio.gather(self.run_receiver(), self.run_pauser())

  async def run_receiver(self):
    while True:
      data = await self.in_topic.recv_data_control()
      if isinstance(data, TopicControlData):
        await self.out_topic.set_paused(data.paused)
      else:
        self.message_trigger.trigger()
        await self.out_topic.set_paused(False)
        await self.out_topic.send(data)

  async def run_pauser(self):
    while True:
      try: await asyncio.wait_for(self.message_trigger.wait(), self.conifg.after_duration)
      except asyncio.TimeoutError: await self.out_topic.set_paused(True)

class PauserTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="pauser",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic" }],
    default_config=PauserConfigBase().model_dump(),
    io_mirror=[("in_topic", 0)],
    editor_fields=[
      EditorFields.number(key="after_duration", label="pause after duration", min_value=0, unit="s"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return PauserTask(await self.create_client(topic_space_id), PauserConfig.model_validate(config))
