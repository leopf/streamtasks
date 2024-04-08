from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.media.util import list_available_codecs, list_pixel_formats
from streamtasks.media.video import VideoCodecInfo, VideoFrame
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import MediaMessage, TimestampChuckMessage
from streamtasks.system.configurators import static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
import numpy as np

class VideoDecoderConfigBase(BaseModel):
  in_pixel_format: str
  out_pixel_format: str
  codec: str
  width: int
  height: int
  rate: int
  
  @staticmethod
  def default_config(): return VideoDecoderConfigBase(in_pixel_format="yuv420p", out_pixel_format="rgb24", codec="h264", width=1280, height=720, rate=30)
  
class VideoDecoderConfig(VideoDecoderConfigBase):
  out_topic: int
  in_topic: int

class VideoDecoderTask(Task):  
  def __init__(self, client: Client, config: VideoDecoderConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config
    codec_info = VideoCodecInfo(
      width=config.width,
      height=config.height,
      frame_rate=config.rate,
      pixel_format=config.out_pixel_format,
      codec=config.codec)
    self.decoder = codec_info.get_decoder()

  async def run(self):
    try:
      async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
        self.client.start()
        while True:
          try:
            data = await self.in_topic.recv_data()
            message = MediaMessage.model_validate(data.data)
            frames: list[VideoFrame] = []
            for packet in message.packets: frames.extend(await self.decoder.decode(packet))
            for frame in frames:
              bm = frame.convert(width=self.config.width, height=self.config.height, pixel_format=self.config.out_pixel_format)
              await self.out_topic.send(MessagePackData(TimestampChuckMessage(timestamp=message.timestamp, data=bm.tobytes("C")).model_dump()))
          except ValidationError: pass
    finally:
      self.encoder.close()
    
class VideoDecoderTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="video decoder",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "bitmap" }],
    default_config=VideoDecoderConfigBase.default_config().model_dump(),
    config_to_input_map={ "in_topic": { **{ v: v for v in [ "rate", "width", "height", "codec" ] }, "in_pixel_format": "pixel_format" } },
    config_to_output_map=[ { **{ v: v for v in [ "rate", "width", "height" ] }, "out_pixel_format": "pixel_format" } ],
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
    return VideoDecoderTask(await self.create_client(topic_space_id), VideoDecoderConfig.model_validate(config))
  