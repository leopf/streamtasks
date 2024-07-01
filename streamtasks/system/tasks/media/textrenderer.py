from contextlib import asynccontextmanager
import glob
import os
import platform
import queue
from typing import Any
from pydantic import BaseModel, ValidationError, field_validator
from streamtasks.media.util import list_pil_pixel_formats, pixel_format_to_pil_mode
from streamtasks.message.types import TextMessage, TimestampChuckMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.net.serialization import RawData
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.utils import context_task
from PIL import Image, ImageDraw, ImageFont

def list_ttf_files():
    font_paths = {
      'Linux': [
        '/usr/share/fonts/**/*.ttf',
        '/usr/local/share/fonts/**/*.ttf',
        os.path.expanduser('~/.fonts/**/*.ttf')
      ],
      'Windows': [
        'C:\\Windows\\Fonts\\**\\*.ttf'
      ],
      'Darwin': [
        '/Library/Fonts/**/*.ttf',
        '/System/Library/Fonts/**/*.ttf',
        os.path.expanduser('~/Library/Fonts/**/*.ttf')
      ]
    }
    return [ os.path.basename(file) for pattern in font_paths.get(platform.system(), []) for file in glob.glob(pattern, recursive=True) ]

class TextRendererConfigBase(BaseModel):
  pixel_format: IOTypes.PixelFormat = "rgba"
  width: IOTypes.Width = 1280
  height: IOTypes.Height = 720
  x: int = 0
  y: int = 0
  font_size: int = 12
  font: str = "Hack-Regular.ttf"
  font_color: str = "#000000"

  @field_validator("font")
  @classmethod
  def validate_font(cls, value: str):
    if value not in list_ttf_files(): raise ValueError("Invalid font filename.")
    return value

class TextRendererConfig(TextRendererConfigBase):
  out_topic: int
  in_topic: int

class TextRendererTask(SyncTask):
  def __init__(self, client: Client, config: TextRendererConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config
    self.message_queue: queue.Queue[TextMessage] = queue.Queue()

  @asynccontextmanager
  async def init(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext(), context_task(self._run_receiver()):
      self.client.start()
      yield

  async def _run_receiver(self):
    while True:
      try:
        data = await self.in_topic.recv_data_control()
        if isinstance(data, TopicControlData): await self.out_topic.set_paused(data.paused)
        else: self.message_queue.put(TextMessage.model_validate(data.data))
      except (ValidationError, ValueError): pass

  def run_sync(self):
    pil_mode = pixel_format_to_pil_mode(self.config.pixel_format)
    font = ImageFont.truetype(self.config.font, size=self.config.font_size)
    while not self.stop_event.is_set():
      try:
        message = self.message_queue.get(timeout=0.5)
        image = Image.new(pil_mode, (self.config.width, self.config.height))
        draw = ImageDraw.Draw(image)
        draw.text((self.config.x, self.config.y), message.value, font=font, fill=self.config.font_color)
        self.send_data(self.out_topic, RawData(TimestampChuckMessage(timestamp=message.timestamp, data=image.tobytes()).model_dump()))
      except queue.Empty: pass

class TextRendererTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="text renderer",
    inputs=[{ "label": "video", "type": "ts", "key": "in_topic", "content": "text" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "video", "codec": "raw", "rate": 0 }],
    default_config=TextRendererConfigBase().model_dump(),
    config_to_output_map=[ { v: v for v in [ "width", "height", "pixel_format" ] } ],
    editor_fields=[
      MediaEditorFields.pixel_format(allowed_values = list_pil_pixel_formats()),
      MediaEditorFields.pixel_size("width"),
      MediaEditorFields.pixel_size("height"),
      MediaEditorFields.pixel_size("x"),
      MediaEditorFields.pixel_size("y"),
      EditorFields.select("font", [ (font_file, os.path.splitext(font_file)[0]) for font_file in list_ttf_files() ]),
      MediaEditorFields.pixel_size("font_size"),
      EditorFields.color("font_color"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return TextRendererTask(await self.create_client(topic_space_id), TextRendererConfig.model_validate(config))
