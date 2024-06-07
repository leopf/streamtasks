from contextlib import asynccontextmanager
from typing import Any
from pydantic import BaseModel, field_validator
from streamtasks.net.serialization import RawData
from streamtasks.message.types import TimestampChuckMessage
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client
import cv2

from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.utils import get_timestamp_ms

class VideoInputConfigBase(BaseModel):
  width: IOTypes.Width
  height: IOTypes.Height
  rate: IOTypes.FrameRate
  pixel_format: str
  camera_id: int

  @field_validator('pixel_format')
  @classmethod
  def pixel_format_must_be_convertable(cls, v: str) -> str:
    if v not in VideoInputTask._COLOR_FORMAT2CV_MAP: raise ValueError('pixel_format must be convertable')
    return v

  @staticmethod
  def default_config(): return VideoInputConfigBase(width=1280, height=720, rate=30, pixel_format="bgr24", camera_id=0)

class VideoInputConfig(VideoInputConfigBase):
  out_topic: int

class VideoInputTask(SyncTask):
  _COLOR_FORMAT2CV_MAP: dict[str, int] = {
    "rgb24": (cv2.COLOR_BGR2RGB,),
    "bgra": (cv2.COLOR_BGR2BGRA,),
    "gray": (cv2.COLOR_BGR2GRAY,),
    "bgr24": ()
  }

  def __init__(self, client: Client, config: VideoInputConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.frame_duration = 1000 / self.config.rate

  @asynccontextmanager
  async def init(self):
    async with self.out_topic, self.out_topic.RegisterContext():
      self.client.start()
      yield

  def run_sync(self):
    try:
      vc = cv2.VideoCapture(self.config.camera_id)
      vc.set(cv2.CAP_PROP_FPS, self.config.rate)
      if not vc.isOpened(): raise Exception(f"Failed to open video capture on id {self.config.camera_id}")
      min_next_timestamp: int | float = 0
      while vc.isOpened() and not self.stop_event.is_set():
        result, frame = vc.read()
        timestamp = max(get_timestamp_ms(), int(min_next_timestamp))
        min_next_timestamp = timestamp + self.frame_duration
        if not result: raise Exception("Failed to read image!")
        frame = cv2.resize(frame, (self.config.width, self.config.height))
        for clr_coversion in VideoInputTask._COLOR_FORMAT2CV_MAP[self.config.pixel_format]: frame = cv2.cvtColor(frame, clr_coversion)
        self.send_data(self.out_topic, RawData(TimestampChuckMessage(timestamp=timestamp, data=frame.tobytes()).model_dump()))
    finally:
      vc.release()

class VideoInputTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="video input",
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "video", "codec": "raw" }],
    default_config=VideoInputConfigBase.default_config().model_dump(),
    config_to_output_map=[ { v: v for v in [ "rate", "pixel_format", "width", "height" ] } ],
    editor_fields=[
      EditorFields.integer(key="camera_id", min_value=0),
      MediaEditorFields.pixel_format(allowed_values=set(VideoInputTask._COLOR_FORMAT2CV_MAP.keys())),
      MediaEditorFields.pixel_size("width"),
      MediaEditorFields.pixel_size("height"),
      MediaEditorFields.frame_rate(),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return VideoInputTask(await self.create_client(topic_space_id), VideoInputConfig.model_validate(config))
