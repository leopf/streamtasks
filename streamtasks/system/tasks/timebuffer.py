import asyncio
from typing import Any, Literal
from pydantic import BaseModel
from streamtasks.rawdatabuffer import RawDataBuffer
from streamtasks.net.messages import TopicControlData
from streamtasks.message.utils import get_timestamp_from_message
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.utils import AsyncTrigger, get_timestamp_ms
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class TimeBufferConfigBase(BaseModel):
  time_reference: Literal["message", "clock"] = "clock"
  size: int = 1000

class TimeBufferConfig(TimeBufferConfigBase):
  out_topic: int
  in_topic: int

class TimeBufferTask(Task):
  def __init__(self, client: Client, config: TimeBufferConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config

    self.update_trigger = AsyncTrigger()
    self.message_queue = RawDataBuffer()
    self.paused = False

  async def run(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      run_sender = self.run_sender_message() if self.config.time_reference == "message" else self.run_sender_clock()
      await asyncio.gather(self.run_receiver(), run_sender)

  async def run_receiver(self):
    while True:
      data = await self.in_topic.recv_data_control()
      if isinstance(data, TopicControlData): self.paused = data.paused
      else: self.message_queue.append(data)
      self.update_trigger.trigger()

  async def run_sender_message(self):
    while True:
      await self.update_trigger.wait()

      while len(self.message_queue) > 1:
        next_message = self.message_queue[0]
        try: next_timestamp = get_timestamp_from_message(next_message)
        except ValueError:
          await self.out_topic.send(self.message_queue.popleft())
          continue

        top_message = self.message_queue[-1]
        try: top_timestamp = get_timestamp_from_message(top_message)
        except ValueError: break

        if top_timestamp - next_timestamp >= self.config.size: await self.out_topic.send(self.message_queue.popleft())
        else: break

      if len(self.message_queue) == 1 and self.paused: await self.out_topic.send(self.message_queue.popleft())
      await self.out_topic.set_paused(self.paused and len(self.message_queue) == 0)

  async def run_sender_clock(self):
    while True:
      if len(self.message_queue) == 0: await self.update_trigger.wait()
      await self.out_topic.set_paused(self.paused and len(self.message_queue) == 0)

      if len(self.message_queue) > 0:
        next_message = self.message_queue[0]
        try:
          next_timestamp = get_timestamp_from_message(next_message)
          pending_ms = self.config.size - (get_timestamp_ms() - next_timestamp)
          if pending_ms > 0: await asyncio.sleep(pending_ms / 1000.)
        except ValueError: pass
        finally: await self.out_topic.send(self.message_queue.popleft())

class TimeBufferTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="time buffer",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic" }],
    default_config=TimeBufferConfigBase().model_dump(),
    io_mirror=[("in_topic", 0)],
    editor_fields=[
      EditorFields.select(key="time_reference", items=[("clock", "system time"), ("message", "message")]),
      EditorFields.integer(key="size", label="buffer size in milliseconds", unit="ms", min_value=1),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return TimeBufferTask(await self.create_client(topic_space_id), TimeBufferConfig.model_validate(config))
