import asyncio
import multiprocessing as mp
from typing import Any, Literal
from pydantic import BaseModel
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import TimestampChuckMessage
from streamtasks.system.configurators import IOTypes, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
import cv2

from streamtasks.utils import get_timestamp_ms, wait_with_dependencies

BitmapPixelFormat = Literal["rgb24"]

class VideoInputConfigBase(BaseModel):
  width: IOTypes.Width
  height: IOTypes.Height
  rate: IOTypes.Rate
  pixel_format: BitmapPixelFormat
  camera_id: int
  
  @staticmethod
  def default_config(): return VideoInputConfigBase(width=1280, height=720, rate=30, pixel_format="rgb24", camera_id=0)

class VideoInputConfig(VideoInputConfigBase):
  out_topic: int

class VideoInputTask(Task):
  _COLOR_FORMAT2CV_MAP: dict[BitmapPixelFormat, int] = {
    "rgb24": cv2.COLOR_BGR2RGB
  }
  
  def __init__(self, client: Client, config: VideoInputConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.message_queue: asyncio.Queue[TimestampChuckMessage] = asyncio.Queue()
    self.config = config
    self.mp_close_event = mp.Event()

  async def run(self):
    try:
      loop = asyncio.get_running_loop()
      recorder_fut = loop.run_in_executor(None, self._run_input_recorder)
      async with self.out_topic, self.out_topic.RegisterContext():
        self.client.start()
        while not recorder_fut.done():
          message: TimestampChuckMessage = await wait_with_dependencies(self.message_queue.get(), [ recorder_fut ])
          await self.out_topic.send(MessagePackData(message.model_dump()))
    finally:
      self.mp_close_event.set()
      await recorder_fut
      
  def _run_input_recorder(self):
    try:
      vc = cv2.VideoCapture(self.config.camera_id)
      if not vc.isOpened(): raise Exception(f"Failed to open video capture on id {self.config.camera_id}")
      while vc.isOpened() and not self.mp_close_event.is_set():
        result, frame = vc.read()
        timestamp = get_timestamp_ms()
        if not result: raise Exception("Failed to read image!")
        frame = cv2.resize(frame, (self.config.width, self.config.height))
        frame = cv2.cvtColor(frame, VideoInputTask._COLOR_FORMAT2CV_MAP[self.config.pixel_format])
        self.message_queue.put_nowait(TimestampChuckMessage(timestamp=timestamp, data=frame.tobytes()))
    finally:
      vc.release()
    
class VideoInputTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="video input",
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "video", "codec": "raw" }],
    default_config=VideoInputConfigBase.default_config().model_dump(),
    config_to_output_map=[ { v: v for v in [ "rate", "pixel_format", "width", "height" ] } ],
    editor_fields=[
      {
        "type": "select",
        "key": "pixel_format",
        "label": "pixel format",
        "items": [ { "label": "RGB 24", "value": "rgb24" } ]
      },
      {
        "type": "number",
        "key": "camera_id",
        "label": "camera id",
        "integer": True,
        "min": 0,
        "max": 256
      },
      {
        "type": "number",
        "key": "width",
        "label": "width",
        "integer": True,
        "min": 0,
        "unit": "px"
      },
      {
        "type": "number",
        "key": "height",
        "label": "height",
        "integer": True,
        "min": 0,
        "unit": "px"
      },
      {
        "type": "number",
        "key": "rate",
        "label": "frame rate",
        "integer": True,
        "min": 0,
        "unit": "fps"
      },
    ]
  )}
  async def create_task(self, config: Any, topic_space_id: int | None):
    return VideoInputTask(await self.create_client(topic_space_id), VideoInputConfig.model_validate(config))
  