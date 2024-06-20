import asyncio
from contextlib import AsyncExitStack
from typing import Any
from typing_extensions import TypedDict
from pydantic import BaseModel, ValidationError
from streamtasks.client.topic import InTopic, SequentialInTopicSynchronizer
from streamtasks.message.types import NumberMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from streamtasks.utils import context_task

class IOPair(TypedDict):
  control: int
  input: int

class SwitchConfig(BaseModel):
  pairs: list[IOPair] = []
  output: int

class SwitchTask(Task):
  def __init__(self, client: Client, config: SwitchConfig):
    super().__init__(client)
    sync = SequentialInTopicSynchronizer()
    self.out_topic = client.out_topic(config.output)
    self.pairs = [ (client.sync_in_topic(pair["input"], sync), client.sync_in_topic(pair["control"], sync)) for pair in config.pairs ]
    self.control_values: dict[int, int | float] = {}

  async def run(self):
    async with AsyncExitStack() as exit_stack:
      await exit_stack.enter_async_context(self.out_topic)
      await exit_stack.enter_async_context(self.out_topic.RegisterContext())

      for idx, (in_topic, control_topic) in enumerate(self.pairs):
        await exit_stack.enter_async_context(in_topic)
        await exit_stack.enter_async_context(in_topic.RegisterContext())
        await exit_stack.enter_async_context(control_topic)
        await exit_stack.enter_async_context(control_topic.RegisterContext())
        await exit_stack.enter_async_context(context_task(self._run_input_receiver(in_topic, idx)))
        await exit_stack.enter_async_context(context_task(self._run_control_receiver(control_topic, idx)))

      self.client.start()
      await asyncio.Future()

  async def _run_input_receiver(self, topic: InTopic, idx: int):
    while True:
      data = await topic.recv_data_control()
      if self._get_selected_index() == idx:
        await self.out_topic.set_paused(topic.is_paused)
        if not isinstance(data, TopicControlData): await self.out_topic.send(data)

  async def _run_control_receiver(self, topic: InTopic, idx: int):
    while True:
      data = await topic.recv_data_control()
      try:
        if isinstance(data, TopicControlData):
          if data.paused: self.control_values.pop(idx, None)
        else:
          message = NumberMessage.model_validate(data.data)
          await self.set_value(idx, message.value)
      except ValidationError: pass

  async def set_value(self, idx: int, value: float | int):
    self.control_values[idx] = value
    selected_index = self._get_selected_index()
    if selected_index != -1:
      await self.out_topic.set_paused(self.pairs[selected_index][0].is_paused)

  def _get_selected_index(self):
    if len(self.control_values) == 0: return -1
    selected_value = max(value for value in self.control_values.values())
    return next(idx for idx, value in self.control_values.items() if value == selected_value)

class SwitchTaskHost(TaskHost):
  @property
  def metadata(self): return {
    "js:configurator": "std:switch",
    "cfg:label": "Switch"
  }
  async def create_task(self, config: Any, topic_space_id: int | None):
    return SwitchTask(await self.create_client(topic_space_id), SwitchConfig.model_validate(config))
