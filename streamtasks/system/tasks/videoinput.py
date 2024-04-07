import asyncio
import multiprocessing as mp
from typing import Any, Literal
from pydantic import BaseModel
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import TimestampChuckMessage
from streamtasks.system.configurators import static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
import cv2

from streamtasks.utils import get_timestamp_ms, wait_with_dependencies

ColorFormat = Literal["rgb24"]

class VideoInputConfig(BaseModel):
  out_topic: int
  camera_id: int
  width: int
  height: int
  rate: int
  color_format: ColorFormat

class VideoInputTask(Task):
  _COLOR_FORMAT2CV_MAP: dict[ColorFormat, int] = {
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
        frame = cv2.cvtColor(frame, VideoInputTask._COLOR_FORMAT2CV_MAP[self.config.color_format])
        self.message_queue.put_nowait(TimestampChuckMessage(timestamp=timestamp, data=frame.tobytes()))
    finally:
      vc.release()
    
class VideoInputTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="video input",
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "width": 1280, "height": 720, "rate": 30, "color_format": "rgb24", "content": "bitmap" }],
    default_config={ "color_format": "rgb24", "width": 720, "height": 1280, "rate": 30, "camera_id": 0 },
    config_to_output_map=[ { v: v for v in [ "rate", "color_format", "width", "height" ] } ],
    editor_fields=[
      {
        "type": "select",
        "key": "color_format",
        "label": "color format",
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
  