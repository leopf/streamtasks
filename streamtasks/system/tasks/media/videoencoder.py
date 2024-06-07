from contextlib import asynccontextmanager
from fractions import Fraction
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.media.video import VideoCodecInfo, VideoFrame, video_buffer_to_ndarray
from streamtasks.net.serialization import RawData
from streamtasks.message.types import MediaMessage, TimestampChuckMessage
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client
import queue

from streamtasks.utils import context_task

class VideoEncoderConfigBase(BaseModel):
  in_pixel_format: IOTypes.PixelFormat = "bgr24"
  out_pixel_format: IOTypes.PixelFormat = "yuv420p"
  encoder: IOTypes.CoderName = "h264"
  codec: IOTypes.CodecName = "h264"
  width: IOTypes.Width = 1280
  height: IOTypes.Height = 720
  rate: IOTypes.FrameRate = 50
  codec_options: dict[str, str] = {}

class VideoEncoderConfig(VideoEncoderConfigBase):
  out_topic: int
  in_topic: int

class VideoEncoderTask(SyncTask):
  def __init__(self, client: Client, config: VideoEncoderConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config

    self.time_base = Fraction(1, config.rate) if int(config.rate) == config.rate else Fraction(1 / config.rate)
    self.t0: int | None = None

    codec_info = VideoCodecInfo(
      width=config.width,
      height=config.height,
      frame_rate=config.rate,
      pixel_format=config.out_pixel_format,
      codec=config.encoder, options=config.codec_options)
    self.encoder = codec_info.get_encoder()

    self.frame_data_queue: queue.Queue[TimestampChuckMessage] = queue.Queue()

  @asynccontextmanager
  async def init(self):
    try:
      async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext(), context_task(self._run_receiver()):
        self.client.start()
        yield
    finally:
      self.encoder.close()

  async def _run_receiver(self):
    while True:
      try:
        data = await self.in_topic.recv_data()
        self.frame_data_queue.put(TimestampChuckMessage.model_validate(data.data))
      except ValidationError: pass

  def run_sync(self):
    timeout = 2 / self.config.rate
    while not self.stop_event.is_set():
      try:
        message = self.frame_data_queue.get(timeout=timeout)
        if self.t0 is None: self.t0 = message.timestamp
        bitmap = video_buffer_to_ndarray(message.data, self.config.width, self.config.height)
        frame = VideoFrame.from_ndarray(bitmap, self.config.in_pixel_format)
        frame.set_ts(Fraction(message.timestamp - self.t0, 1000), self.time_base)
        packets = self.encoder.encode_sync(frame)
        for packet in packets:
          self.send_data(self.out_topic, RawData(MediaMessage(timestamp=int(self.t0 + packet.dts * self.time_base * 1000), packet=packet).model_dump()))
        self.frame_data_queue.task_done()
      except queue.Empty: pass

class VideoEncoderTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="video encoder",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "content": "video", "codec": "raw" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "video" }],
    default_config=VideoEncoderConfigBase().model_dump(),
    config_to_input_map={ "in_topic": { **{ v: v for v in [ "rate", "width", "height" ] }, "in_pixel_format": "pixel_format" } },
    config_to_output_map=[ { **{ v: v for v in [ "rate", "width", "height", "codec" ] }, "out_pixel_format": "pixel_format" } ],
    editor_fields=[
      MediaEditorFields.pixel_format("in_pixel_format", "input pixel format"),
      MediaEditorFields.pixel_format("out_pixel_format", "output pixel format"),
      MediaEditorFields.video_codec("w", coder_key="encoder"),
      MediaEditorFields.pixel_size("width"),
      MediaEditorFields.pixel_size("height"),
      MediaEditorFields.frame_rate(),
      EditorFields.options("codec_options"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return VideoEncoderTask(await self.create_client(topic_space_id), VideoEncoderConfig.model_validate(config))
