from fractions import Fraction
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.media.video import VideoFrame, VideoReformatter, VideoReformatterInfo
from streamtasks.net.serialization import RawData
from streamtasks.message.types import TimestampChuckMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.system.configurators import IOTypes, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class VideoReformatterConfigBase(BaseModel):
  in_pixel_format: IOTypes.PixelFormat = "bgr24"
  in_rate: IOTypes.FrameRate = 30
  in_width: IOTypes.Width = 1280
  in_height: IOTypes.Height = 720

  out_pixel_format: IOTypes.PixelFormat = "bgr24"
  out_rate: IOTypes.FrameRate = 30
  out_width: IOTypes.Width = 1280
  out_height: IOTypes.Height = 720

class VideoReformatterConfig(VideoReformatterConfigBase):
  out_topic: int
  in_topic: int

class VideoReformatterTask(Task):
  def __init__(self, client: Client, config: VideoReformatterConfig):
    super().__init__(client)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.reformatter = VideoReformatter(
      VideoReformatterInfo(self.config.out_rate, self.config.out_pixel_format, self.config.out_width, self.config.out_height),
      VideoReformatterInfo(self.config.in_rate, self.config.in_pixel_format, self.config.in_width, self.config.in_height),
    )

  async def run(self):
    t0: int | None = None
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      while True:
        try:
          data = await self.in_topic.recv_data_control()
          if isinstance(data, TopicControlData): await self.out_topic.set_paused(data.paused)
          else:
            message = TimestampChuckMessage.model_validate(data.data)
            if t0 is None: t0 = message.timestamp
            frame = VideoFrame.from_buffer(message.data, self.config.in_width, self.config.in_height, self.config.in_pixel_format)
            frame.set_ts(Fraction(message.timestamp - t0, 1000), Fraction(1, self.config.in_rate))
            for nframe in await self.reformatter.reformat(frame):
              await self.out_topic.send(RawData(TimestampChuckMessage(timestamp=int(nframe.dtime * 1000) + t0, data=nframe.to_bytes()).model_dump()))
        except (ValidationError, ValueError): pass

class VideoReformatterTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="video reformatter",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "content": "video", "codec": "raw" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "video", "codec": "raw" }],
    default_config=VideoReformatterConfigBase().model_dump(),
    config_to_input_map={ "in_topic": { f"in_{v}": v for v in [ "rate", "pixel_format", "width", "height" ] } },
    config_to_output_map=[ { f"out_{v}": v for v in [ "rate", "pixel_format", "width", "height" ] } ],
    editor_fields=[
      MediaEditorFields.pixel_format(key="in_pixel_format", label="input pixel format"),
      MediaEditorFields.frame_rate(key="in_rate", label="input frame rate"),
      MediaEditorFields.pixel_size(key="in_width", label="input width"),
      MediaEditorFields.pixel_size(key="in_height", label="input height"),
      MediaEditorFields.pixel_format(key="out_pixel_format", label="output pixel format"),
      MediaEditorFields.frame_rate(key="out_rate", label="output frame rate"),
      MediaEditorFields.pixel_size(key="out_width", label="output width"),
      MediaEditorFields.pixel_size(key="out_height", label="output height"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return VideoReformatterTask(await self.create_client(topic_space_id), VideoReformatterConfig.model_validate(config))
