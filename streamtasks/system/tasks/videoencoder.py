import asyncio
import multiprocessing as mp
from typing import Any, Literal
from pydantic import BaseModel
from streamtasks.media.util import list_available_codecs, list_pixel_formats
from streamtasks.media.video import VideoCodecInfo, VideoFrame
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import TimestampChuckMessage
from streamtasks.system.configurators import static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
import numpy as np

from streamtasks.utils import get_timestamp_ms, wait_with_dependencies

class VideoEncoderConfig(BaseModel):
  out_topic: int
  in_topic: int
  in_pixel_format: str
  out_pixel_format: str
  codec: str
  width: int
  height: int
  rate: int

class VideoEncoderTask(Task):  
  def __init__(self, client: Client, config: VideoEncoderConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config
    codec_info = VideoCodecInfo(
      width=config.width,
      height=config.height,
      framerate=config.rate,
      pixel_format=config.out_pixel_format,
      codec=config.codec)
    self.encoder = codec_info.get_encoder()

  async def run(self):
    try:
      async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
        while True:
          data = await self.in_topic.recv_data()
          message = TimestampChuckMessage.model_validate(data)
          buf = np.frombuffer(data.data, dtype=np.uint8)
          buf = buf.reshape((self.codec_info.width, self.codec_info.height, -1))
          frame = VideoFrame.from_ndarray(buf, self.config.in_pixel_format)
          packets = await self.encoder.encode(frame)
          for packet in packets:
            await self.out_topic.send(MessagePackData({
              "timestamp": message.timestamp,
              **packet.as_dict()
            }))
    finally:
      pass
    
class VideoEncoderTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="video encoder",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "width": 1280, "height": 720, "rate": 30, "pixel_format": "rgb24", "content": "bitmap" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "width": 1280, "height": 720, "rate": 30 }],
    default_config={ "in_pixel_format": "rgb24", "out_pixel_format": "rgb24", "codec": "h264", "width": 720, "height": 1280, "rate": 30 },
    config_to_input_map={ "in_topic": { **{ v: v for v in [ "rate", "width", "height" ] }, "in_pixel_format": "pixel_format" } },
    config_to_output_map=[ { **{ v: v for v in [ "rate", "width", "height", "codec" ] }, "out_pixel_format": "pixel_format" } ],
    editor_fields=[
      {
        "type": "select",
        "key": "in_pixel_format",
        "label": "input pixel format",
        "items": [ { "label": pxl_fmt.upper(), "value": pxl_fmt } for pxl_fmt in list_pixel_formats() ]
      },
      {
        "type": "select",
        "key": "out_pixel_format",
        "label": "output pixel format",
        "items": [ { "label": pxl_fmt.upper(), "value": pxl_fmt } for pxl_fmt in list_pixel_formats() ]
      },
      {
        "type": "select",
        "key": "codec",
        "label": "codec",
        "items": [ { "label": codec.name.upper(), "value": codec.name } for codec in sorted(list_available_codecs("w"), key=lambda sc: sc.name) if codec.type == "video" ]
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
    return VideoEncoderTask(await self.create_client(topic_space_id), VideoEncoderConfig.model_validate(config))
  