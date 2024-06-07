from contextlib import asynccontextmanager
import queue
from typing import Any
import numpy as np
from pydantic import BaseModel, ValidationError
from streamtasks.media.video import video_buffer_to_ndarray
from streamtasks.net.serialization import RawData
from streamtasks.message.types import NumberMessage, TimestampChuckMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.configurators import IOTypes, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client

from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.utils import TimeSynchronizer, context_task

class VideoActivityMeterConfigBase(BaseModel):
  pixel_format: IOTypes.PixelFormat = "bgr24"
  width: IOTypes.Width = 1280
  height: IOTypes.Height = 720
  rate: IOTypes.FrameRate = 30

class VideoActivityMeterConfig(VideoActivityMeterConfigBase):
  out_topic: int
  in_topic: int

class VideoActivityMeterTask(SyncTask):
  def __init__(self, client: Client, config: VideoActivityMeterConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config
    self.sync = TimeSynchronizer()
    self.message_queue: queue.Queue[TimestampChuckMessage] = queue.Queue()

  @asynccontextmanager
  async def init(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext(), context_task(self._run_receiver()):
      self.client.start()
      yield

  async def _run_receiver(self):
    sync = TimeSynchronizer()
    while True:
      try:
        data = await self.in_topic.recv_data_control()
        if isinstance(data, TopicControlData):
          if data.paused: await self.out_topic.send(RawData(NumberMessage(timestamp=sync.time, value=0).model_dump()))
          await self.out_topic.set_paused(data.paused)
        else:
          message = TimestampChuckMessage.model_validate(data.data)
          sync.update(message.timestamp)
          self.message_queue.put(message)
      except (ValidationError, ValueError): pass

  def run_sync(self):
    last_bitmap: None | np.ndarray = None
    timeout = 2 / self.config.rate
    while not self.stop_event.is_set():
      try:
        message = self.message_queue.get(timeout=timeout)
        bitmap = video_buffer_to_ndarray(message.data, self.config.width, self.config.height)
        if last_bitmap is not None:
          self.send_data(self.out_topic, RawData(NumberMessage(timestamp=message.timestamp, value=np.abs(last_bitmap - bitmap).flatten().mean()).model_dump()))
        last_bitmap = bitmap
      except queue.Empty: pass

class VideoActivityMeterTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="video activity meter",
    inputs=[{ "label": "video", "type": "ts", "key": "in_topic", "content": "video", "codec": "raw" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "number" }],
    default_config=VideoActivityMeterConfigBase().model_dump(),
    config_to_input_map={ "in_topic": { **{ v: v for v in [ "rate", "width", "height", "pixel_format" ] } } },
    editor_fields=[
      MediaEditorFields.pixel_format(),
      MediaEditorFields.pixel_size("width"),
      MediaEditorFields.pixel_size("height"),
      MediaEditorFields.frame_rate(),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return VideoActivityMeterTask(await self.create_client(topic_space_id), VideoActivityMeterConfig.model_validate(config))
