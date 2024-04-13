from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.media.container import InputContainer
from streamtasks.media.video import VideoCodecInfo
from streamtasks.net.message.data import MessagePackData
from streamtasks.system.configurators import IOTypes, static_configurator
from streamtasks.net.message.structures import MediaMessage
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.utils import get_timestamp_ms

class InputContainerConfigBase(BaseModel):
  source: str
  pixel_format: IOTypes.PixelFormat
  codec: IOTypes.Codec
  width: IOTypes.Width
  height: IOTypes.Height
  rate: IOTypes.Rate
  container_options: dict[str, str]
  transcode: bool

  @staticmethod
  def default_config(): return InputContainerConfigBase(source="", pixel_format="yuv420p", codec="h264", width=1280, height=720, rate=30, transcode=False, container_options={})

class InputContainerConfig(InputContainerConfigBase):
  out_topic: int

class InputContainerTask(Task):
  def __init__(self, client: Client, config: InputContainerConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.codec_info = VideoCodecInfo(self.config.width, self.config.height, self.config.rate, self.config.pixel_format, self.config.codec)

  async def run(self):
    try:
      container = None
      container = InputContainer(self.config.source, **self.config.container_options)
      video_stream = container.get_video_stream(0, self.config.transcode)
      if not self.codec_info.compatible_with(video_stream.codec_info): raise ValueError("Codec not compatible with input container")
      
      async with self.out_topic, self.out_topic.RegisterContext():
        self.client.start()
        while True:
          try:
            packets = await video_stream.demux()
            if len(packets) > 0:
              await self.out_topic.send(MessagePackData(MediaMessage(timestamp=get_timestamp_ms(), packets=packets))) # TODO: better timestamp
          except ValidationError: pass
    finally:
      if container is not None: await container.close()

class InputContainerTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="input container",
    outputs=[{ "label": "input", "type": "ts", "key": "out_topic" }],
    default_config=InputContainerConfigBase.default_config().model_dump(),
    config_to_output_map=[ { **{ v: v for v in [ "rate", "width", "height", "codec", "pixel_format" ] } } ],
    editor_fields=[
      {
        "type": "text",
        "key": "source",
        "label": "source path or url",
      },
      MediaEditorFields.pixel_format(),
      MediaEditorFields.video_codec_name("r"),
      MediaEditorFields.pixel_size("width"),
      MediaEditorFields.pixel_size("height"),
      MediaEditorFields.frame_rate(),
      {
        "type": "boolean",
        "key": "transcode",
        "label": "transcode outputs",
      },
      MediaEditorFields.options("container_options"),
    ])}
  async def create_task(self, config: Any, topic_space_id: int | None):
    return InputContainerTask(await self.create_client(topic_space_id), InputContainerConfig.model_validate(config))
