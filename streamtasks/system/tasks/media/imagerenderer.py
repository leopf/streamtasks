import asyncio
import os
import queue
from typing import Any
from pydantic import BaseModel, field_validator
from streamtasks.media.util import list_pil_pixel_formats, pixel_format_to_pil_mode
from streamtasks.message.types import TextMessage, TimestampChuckMessage
from streamtasks.net.serialization import RawData
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.utils import get_timestamp_ms
from PIL import Image

class ImageRendererConfigBase(BaseModel):
  source: str = ""
  pixel_format: IOTypes.PixelFormat = "rgb24"
  width: IOTypes.Width = 1280
  height: IOTypes.Height = 720
  repeat_interval: float = 1

  @field_validator("source")
  @classmethod
  def validate_source(cls, value: str):
    if not os.path.exists(value): raise ValueError("File not found!")
    return value

class ImageRendererConfig(ImageRendererConfigBase):
  out_topic: int

class ImageRendererTask(Task):
  def __init__(self, client: Client, config: ImageRendererConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.message_queue: queue.Queue[TextMessage] = queue.Queue()

  async def run(self):
    img_data = await asyncio.to_thread(self.load_image_data)
    async with self.out_topic, self.out_topic.RegisterContext():
      self.client.start()
      while True:
        await self.out_topic.send(RawData(TimestampChuckMessage(timestamp=get_timestamp_ms(), data=img_data).model_dump()))
        await asyncio.sleep(self.config.repeat_interval)

  def load_image_data(self):
    return Image.open(self.config.source).convert(pixel_format_to_pil_mode(self.config.pixel_format)).resize((self.config.width, self.config.height)).tobytes()

class ImageRendererTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="image renderer",
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "video", "codec": "raw", "rate": 0 }],
    default_config=ImageRendererConfigBase().model_dump(),
    config_to_output_map=[ { v: v for v in [ "width", "height", "pixel_format" ] } ],
    editor_fields=[
      EditorFields.filepath(key="source", label="image path"),
      MediaEditorFields.pixel_format(allowed_values = list_pil_pixel_formats()),
      MediaEditorFields.pixel_size("width"),
      MediaEditorFields.pixel_size("height"),
      EditorFields.repeat_interval(),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return ImageRendererTask(await self.create_client(topic_space_id), ImageRendererConfig.model_validate(config))
