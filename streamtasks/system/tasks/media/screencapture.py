from contextlib import asynccontextmanager
from typing import Any
import numpy as np
from pydantic import BaseModel
from streamtasks.net.serialization import RawData
from streamtasks.message.types import TimestampChuckMessage
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.utils import get_timestamp_ms
import time
import mss

class ScreenCaptureConfigBase(BaseModel):
  left_offset: IOTypes.Width = 0
  top_offset: IOTypes.Height = 0
  width: IOTypes.Width = 1920
  height: IOTypes.Height = 1080
  rate: IOTypes.FrameRate = 30
  set_alpha: int = 255
  display: str = ""
  with_cursor: bool = True

class ScreenCaptureConfig(ScreenCaptureConfigBase):
  out_topic: int

class ScreenCaptureTask(SyncTask):
  def __init__(self, client: Client, config: ScreenCaptureConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config

  @asynccontextmanager
  async def init(self):
    async with self.out_topic, self.out_topic.RegisterContext():
      self.client.start()
      yield

  def run_sync(self):
    frame_count = 0
    start_time = time.time()
    frame_time = 1.0 / self.config.rate
    with mss.mss(with_cursor=self.config.with_cursor, display=self.config.display or None) as sct:
      while not self.stop_event.is_set():
        wait_dur = ((frame_count + 1) * frame_time + start_time) - time.time()
        if wait_dur > 0: time.sleep(wait_dur)
        img = sct.grab((self.config.left_offset, self.config.top_offset, self.config.width, self.config.height))
        if self.config.set_alpha != 0:
          arr = np.ndarray((self.config.height* self.config.width, 4), dtype=np.uint8, buffer=memoryview(img.raw))
          arr[:,3] = self.config.set_alpha
        self.send_data(self.out_topic, RawData(TimestampChuckMessage(timestamp=get_timestamp_ms(), data=img.raw).model_dump()))
        frame_count += 1

class ScreenCaptureTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="screen capture",
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "video", "codec": "raw", "pixel_format": "bgra" }],
    default_config=ScreenCaptureConfigBase().model_dump(),
    config_to_output_map=[ { v: v for v in [ "rate", "width", "height" ] } ],
    editor_fields=[
      MediaEditorFields.pixel_size("top_offset"),
      MediaEditorFields.pixel_size("left_offset"),
      MediaEditorFields.pixel_size("width"),
      MediaEditorFields.pixel_size("height"),
      MediaEditorFields.frame_rate(),
      EditorFields.integer(key="set_alpha", label="set alpha (0=use native)", min_value=0, max_value=255),
      EditorFields.text(key="display"),
      EditorFields.boolean(key="with_cursor")
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return ScreenCaptureTask(await self.create_client(topic_space_id), ScreenCaptureConfig.model_validate(config))
