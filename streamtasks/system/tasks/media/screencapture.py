import asyncio
import multiprocessing as mp
import time
from typing import Any
from pydantic import BaseModel
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import TimestampChuckMessage
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
import mss

from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.utils import get_timestamp_ms, wait_with_dependencies

class ScreenCaptureConfigBase(BaseModel):
  left_offset: IOTypes.Width = 0
  top_offset: IOTypes.Height = 0
  width: IOTypes.Width = 1920
  height: IOTypes.Height = 1080
  rate: IOTypes.FrameRate = 30
  display: str = ""
  with_cursor: bool = True

class ScreenCaptureConfig(ScreenCaptureConfigBase):
  out_topic: int

class ScreenCaptureTask(Task):
  def __init__(self, client: Client, config: ScreenCaptureConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.message_queue: asyncio.Queue[TimestampChuckMessage] = asyncio.Queue()
    self.config = config
    self.mp_close_event = mp.Event()

  async def run(self):
    try:
      loop = asyncio.get_running_loop()
      grapper_fut = loop.run_in_executor(None, self._run_input_recorder, loop)
      async with self.out_topic, self.out_topic.RegisterContext():
        self.client.start()
        while not grapper_fut.done():
          message: TimestampChuckMessage = await wait_with_dependencies(self.message_queue.get(), [ grapper_fut ])
          await self.out_topic.send(MessagePackData(message.model_dump()))
    finally:
      self.mp_close_event.set()
      await grapper_fut

  def _run_input_recorder(self, loop: asyncio.BaseEventLoop):
    frame_count = 0
    start_time = time.time()
    frame_time = 1.0 / self.config.rate
    with mss.mss(with_cursor=self.config.with_cursor, display=self.config.display or None) as sct:
      while not self.mp_close_event.is_set():
        wait_dur = ((frame_count + 1) * frame_time + start_time) - time.time()
        if wait_dur > 0: time.sleep(wait_dur)
        img = sct.grab((self.config.left_offset, self.config.top_offset, self.config.width, self.config.height))
        loop.call_soon_threadsafe(self.message_queue.put_nowait, TimestampChuckMessage(timestamp=get_timestamp_ms(), data=img.bgra))
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
      EditorFields.text(key="display"),
      EditorFields.boolean(key="with_cursor")
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return ScreenCaptureTask(await self.create_client(topic_space_id), ScreenCaptureConfig.model_validate(config))
