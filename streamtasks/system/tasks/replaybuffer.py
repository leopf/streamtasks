import asyncio
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.message.types import NumberMessage
from streamtasks.rawdatabuffer import RawDataBuffer
from streamtasks.net.messages import TopicControlData
from streamtasks.message.utils import get_timestamp_from_message, set_timestamp_on_message
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.utils import TimeSynchronizer
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class ReplayBufferConfigBase(BaseModel):
  loop: bool = False

class ReplayBufferConfig(ReplayBufferConfigBase):
  out_topic: int
  in_topic: int
  play_topic: int

class ReplayBufferTask(Task):
  def __init__(self, client: Client, config: ReplayBufferConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.play_topic = self.client.in_topic(config.play_topic)
    self.config = config
    self.sync = TimeSynchronizer()
    self.buffer = RawDataBuffer()
    self.playing = False
    self.play_task: asyncio.Task | None = None

  async def run(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext(), self.play_topic, self.play_topic.RegisterContext():
      self.client.start()
      await asyncio.gather(self.run_input_receiver(), self.run_play_receiver())

  async def run_input_receiver(self):
    last_paused = False
    while True:
      data = await self.in_topic.recv_data_control()
      if isinstance(data, TopicControlData):
        if not data.paused and last_paused:
          self.buffer.clear()
          await self.stop_play()
        last_paused = data.paused
      else:
        self.buffer.append(data)
        await self.update_playing_state()

  async def run_play_receiver(self):
    while True:
      try:
        data = await self.play_topic.recv_data()
        message = NumberMessage.model_validate(data.data)
        self.sync.update(message.timestamp)
        self.playing = message.value > 0.5
        await self.update_playing_state()
      except ValidationError: pass

  async def play(self):
    await self.out_topic.set_paused(False)
    while True:
      time_offset: int | None = None
      for data in self.buffer:
        data = data.copy()
        try:
          ts = get_timestamp_from_message(data)
          if time_offset is None: time_offset = self.sync.time - ts
          set_timestamp_on_message(data, ts + time_offset)
          wait_time = ((ts + time_offset) - self.sync.time) / 1000
          if wait_time > 0: await asyncio.sleep(wait_time)
        except ValueError: pass
        await self.out_topic.send(data)
      if not self.config.loop: break
    await self.out_topic.set_paused(True)

  async def update_playing_state(self):
    if self.playing and self.play_task is None and len(self.buffer) > 0: self.play_task = asyncio.create_task(self.play())
    if not self.playing:
      await self.out_topic.set_paused(True)
      await self.stop_play()

  async def stop_play(self):
    if self.play_task is not None:
      if not self.play_task.done():
        self.play_task.cancel()
        try: await self.play_task
        except asyncio.CancelledError: pass
      self.play_task = None

class ReplayBufferTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="replay buffer",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic" }, { "label": "play", "type": "ts", "key": "play_topic", "content": "number" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic" }],
    default_config=ReplayBufferConfigBase().model_dump(),
    io_mirror=[("in_topic", 0)],
    editor_fields=[
      EditorFields.boolean(key="loop")
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return ReplayBufferTask(await self.create_client(topic_space_id), ReplayBufferConfig.model_validate(config))
