import asyncio
from contextlib import AsyncExitStack
from typing import Any
from pydantic import BaseModel
from streamtasks.client.topic import InTopic, OutTopic, SequentialInTopicSynchronizer
from streamtasks.net.messages import TopicControlData
from streamtasks.utils import context_task
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class SynchronizerConfig(BaseModel):
   topics: list[tuple[int, int]] = []

class SynchronizerTask(Task):
  def __init__(self, client: Client, config: SynchronizerConfig):
    super().__init__(client)
    sync = SequentialInTopicSynchronizer()
    self.topics = [ (client.sync_in_topic(in_tid, sync), client.out_topic(out_tid)) for in_tid, out_tid in config.topics ]

  async def run(self):
    async with AsyncExitStack() as exit_stack:
      for in_topic, out_topic in self.topics:
        await exit_stack.enter_async_context(in_topic)
        await exit_stack.enter_async_context(in_topic.RegisterContext())
        await exit_stack.enter_async_context(out_topic)
        await exit_stack.enter_async_context(out_topic.RegisterContext())
        await exit_stack.enter_async_context(context_task(self._run_stream(in_topic, out_topic)))
      self.client.start()
      await asyncio.Future()

  async def _run_stream(self, in_topic: InTopic, out_topic: OutTopic):
    while True:
      data = await in_topic.recv_data_control()
      if isinstance(data, TopicControlData): await out_topic.set_paused(data.paused)
      else: await out_topic.send(data)

class SynchronizerTaskHost(TaskHost):
  @property
  def metadata(self): return {
    "js:configurator": "std:synchronizer",
    "cfg:label": "Synchronizer"
  }
  async def create_task(self, config: Any, topic_space_id: int | None):
    return SynchronizerTask(await self.create_client(topic_space_id), SynchronizerConfig.model_validate(config))
