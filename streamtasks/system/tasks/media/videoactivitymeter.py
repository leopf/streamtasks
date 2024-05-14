from typing import Any
import numpy as np
from pydantic import BaseModel, ValidationError
from streamtasks.media.video import video_buffer_to_ndarray
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import NumberMessage, TimestampChuckMessage
from streamtasks.system.configurators import IOTypes, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

from streamtasks.system.tasks.media.utils import MediaEditorFields

class VideoActivityMeterConfigBase(BaseModel):
  pixel_format: IOTypes.PixelFormat = "bgr24"
  width: IOTypes.Width = 1280
  height: IOTypes.Height = 720

class VideoActivityMeterConfig(VideoActivityMeterConfigBase):
  out_topic: int
  in_topic: int

class VideoActivityMeterTask(Task):  
  def __init__(self, client: Client, config: VideoActivityMeterConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config
    self._last_bitmap: np.ndarray | None = None

  async def run(self):
    try:
      async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
        self.client.start()
        while True:
          try:
            data = await self.in_topic.recv_data()
            message = TimestampChuckMessage.model_validate(data.data)
            bitmap = video_buffer_to_ndarray(message.data, self.config.width, self.config.height)
            if self._last_bitmap is not None:
              await self.out_topic.send(MessagePackData(NumberMessage(timestamp=message.timestamp, value=np.abs(self._last_bitmap - bitmap).flatten().mean()).model_dump()))
            self._last_bitmap = bitmap
          except ValidationError: pass
    finally:
      self._last_bitmap = None
    
class VideoActivityMeterTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="video activity meter",
    inputs=[{ "label": "video", "type": "ts", "key": "in_topic", "content": "video", "codec": "raw" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "number" }],
    default_config={**VideoActivityMeterConfigBase().model_dump(), "rate": 30 },
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
  