from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.media.container import OutputContainer
from streamtasks.media.util import list_pixel_formats, list_sorted_available_codecs
from streamtasks.media.video import VideoCodecInfo
from streamtasks.system.configurators import IOTypes, static_configurator
from streamtasks.net.message.structures import MediaMessage
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class OutputContainerConfigBase(BaseModel):
  destination: str
  pixel_format: IOTypes.PixelFormat
  codec: IOTypes.Codec
  width: IOTypes.Width
  height: IOTypes.Height
  rate: IOTypes.Rate
  container_options: dict[str, str]

  @staticmethod
  def default_config(): return OutputContainerConfigBase(destination="", pixel_format="yuv420p", codec="h264", width=1280, height=720, rate=30, container_options={})

class OutputContainerConfig(OutputContainerConfigBase):
  in_topic: int

class OutputContainerTask(Task):
  def __init__(self, client: Client, config: OutputContainerConfig):
    super().__init__(client)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config

  async def run(self):
    try:
      container = None
      container = OutputContainer(self.config.destination, **self.config.container_options)
      video_stream = container.add_video_stream(VideoCodecInfo(self.config.width, self.config.height, self.config.rate, self.config.pixel_format, self.config.codec))
      async with self.in_topic, self.in_topic.RegisterContext():
        self.client.start()
        while True:
          try:
            data = await self.in_topic.recv_data()
            message = MediaMessage.model_validate(data.data)
            for packet in message.packets: await video_stream.mux(packet)
          except ValidationError: pass
    finally:
      if container is not None: await container.close()

class OutputContainerTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="output container",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic" }],
    default_config=OutputContainerConfigBase.default_config().model_dump(),
    config_to_input_map={ "in_topic": { **{ v: v for v in [ "rate", "width", "height", "codec", "pixel_format" ] } } },
    editor_fields=[
      {
        "type": "text",
        "key": "destination",
        "label": "destination path or url",
      },
      {
        "type": "select",
        "key": "pixel_format",
        "label": "pixel format",
        "items": [ { "label": pxl_fmt.upper(), "value": pxl_fmt } for pxl_fmt in list_pixel_formats() ]
      },
      {
        "type": "select",
        "key": "codec",
        "label": "codec",
        "items": [ { "label": codec.name.upper(), "value": codec.name } for codec in list_sorted_available_codecs("w") if codec.type == "video" ]
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
      {
        "type": "kvoptions",
        "key": "container_options",
        "label": "container options",
      }
    ])}
  async def create_task(self, config: Any, topic_space_id: int | None):
    return OutputContainerTask(await self.create_client(topic_space_id), OutputContainerConfig.model_validate(config))
