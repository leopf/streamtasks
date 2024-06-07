from contextlib import asynccontextmanager
import queue
from typing import Any, Self
import cv2
import numpy as np
from pydantic import BaseModel, ValidationError, field_validator, model_validator
from streamtasks.media.video import TRANSPARENT_PXL_FORMATS, video_buffer_to_ndarray
from streamtasks.net.serialization import RawData
from streamtasks.message.types import TimestampChuckMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.system.configurators import IOTypes, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client
from streamtasks.utils import context_task

class VideoLayoutConfigBase(BaseModel):
  pixel_format: IOTypes.PixelFormat = "bgra"
  rate: IOTypes.FrameRate = 30
  in_width: IOTypes.Width = 1280
  in_height: IOTypes.Height = 720

  place_top_offset: IOTypes.Width = 0
  place_left_offset: IOTypes.Width = 0
  place_width: IOTypes.Width = 1280
  place_height: IOTypes.Height = 720

  out_width: IOTypes.Width = 1280
  out_height: IOTypes.Height = 720

  @property
  def apply_width(self): return min(self.place_width, self.out_width - self.place_left_offset)

  @property
  def apply_height(self): return min(self.place_height, self.out_height - self.place_top_offset)

  @model_validator(mode='after')
  def check_passwords_match(self) -> Self:
    if self.place_top_offset < 0 or self.place_top_offset >= self.out_height: raise ValueError("Image must be placed within the output frame (top offset)!")
    if self.place_left_offset < 0 or self.place_left_offset >= self.out_width: raise ValueError("Image must be placed within the output frame (left offset)!")
    return self

  @field_validator("pixel_format")
  @classmethod
  def validate_pixel_format(cls, v: str):
    if v not in TRANSPARENT_PXL_FORMATS: raise ValueError("Invalid pixel format!")
    return v

class VideoLayoutConfig(VideoLayoutConfigBase):
  out_topic: int
  in_topic: int

class VideoLayoutTask(SyncTask):
  def __init__(self, client: Client, config: VideoLayoutConfig):
    super().__init__(client)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.message_queue: queue.Queue[TimestampChuckMessage] = queue.Queue()

  @asynccontextmanager
  async def init(self):
    async with self.in_topic, self.in_topic.RegisterContext(), self.out_topic, self.out_topic.RegisterContext(), context_task(self._run_receiver()):
      self.client.start()
      yield

  async def _run_receiver(self):
    while True:
      try:
        data = await self.in_topic.recv_data_control()
        if isinstance(data, TopicControlData):
          await self.out_topic.set_paused(data.paused)
        else:
          message = TimestampChuckMessage.model_validate(data.data)
          self.message_queue.put(message)
      except (ValidationError, ValueError): pass

  def run_sync(self):
    timeout = 2 / self.config.rate
    while not self.stop_event.is_set():
      try:
        message = self.message_queue.get(timeout=timeout)
        arr = video_buffer_to_ndarray(message.data, self.config.in_width, self.config.in_height)
        arr = cv2.resize(arr, (self.config.place_width, self.config.place_height), interpolation=cv2.INTER_LINEAR)
        arr = arr[:self.config.apply_height,:self.config.apply_width,:]
        assert arr.dtype == np.uint8, "not uint8"
        out_data = np.zeros((self.config.out_height, self.config.out_width, 4), dtype=np.uint8)
        out_data[self.config.place_top_offset:self.config.place_top_offset + arr.shape[0], self.config.place_left_offset:self.config.place_left_offset + arr.shape[1]] = arr
        self.send_data(self.out_topic, RawData(TimestampChuckMessage(timestamp=message.timestamp, data=out_data.tobytes("C")).model_dump()))
      except queue.Empty: pass

class VideoLayoutTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="video layout",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "content": "video", "codec": "raw" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "video", "codec": "raw" }],
    default_config=VideoLayoutConfigBase().model_dump(),
    config_to_input_map={ "in_topic": { v: v for v in [ "rate", "pixel_format" ] } | { "in_width": "width", "in_height": "height" } },
    config_to_output_map=[ { v: v for v in [ "rate", "pixel_format" ] } | { "out_width": "width", "out_height": "height" } ],
    editor_fields=[
      MediaEditorFields.pixel_format(allowed_values = TRANSPARENT_PXL_FORMATS),
      MediaEditorFields.frame_rate(),
      MediaEditorFields.pixel_size(key="place_top_offset"),
      MediaEditorFields.pixel_size(key="place_left_offset"),
      MediaEditorFields.pixel_size(key="place_width"),
      MediaEditorFields.pixel_size(key="place_height"),
      MediaEditorFields.pixel_size(key="in_width", label="input width"),
      MediaEditorFields.pixel_size(key="in_height", label="input height"),
      MediaEditorFields.pixel_size(key="out_width", label="output width"),
      MediaEditorFields.pixel_size(key="out_height", label="output height"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return VideoLayoutTask(await self.create_client(topic_space_id), VideoLayoutConfig.model_validate(config))
