import asyncio
from fractions import Fraction
import json
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.media.container import OutputContainer
from streamtasks.media.video import VideoCodecInfo
from streamtasks.system.configurators import IOTypes, static_configurator
from streamtasks.net.message.structures import MediaMessage
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from streamtasks.system.tasks.media.utils import MediaEditorFields

class ContainerVideoOutputConfig(BaseModel):
  pixel_format: IOTypes.PixelFormat
  codec: IOTypes.Codec
  width: IOTypes.Width
  height: IOTypes.Height
  rate: IOTypes.Rate
  codec_options: dict[str, str]
  in_topic: int

class OutputContainerConfig(BaseModel):
  destination: str
  videos: list[ContainerVideoOutputConfig]
  container_options: dict[str, str]

  @staticmethod
  def default_config(): return OutputContainerConfig(destination="", videos=[], container_options={})

class OutputContainerTask(Task):
  def __init__(self, client: Client, config: OutputContainerConfig):
    super().__init__(client)
    self.config = config

  async def _run_video(self, config: ContainerVideoOutputConfig, container: OutputContainer):
    stream = container.add_video_stream(VideoCodecInfo(
      width=config.width, height=config.height, frame_rate=config.rate,
      pixel_format=config.pixel_format, codec=config.codec, options=config.codec_options))
    
    in_topic = self.client.in_topic(config.in_topic)
    start_time: int | None = None
    async with in_topic, in_topic.RegisterContext():
      while True:
        try:
          data = await self.in_topic.recv_data()
          message = MediaMessage.model_validate(data.data)
          start_time = start_time or message.timestamp
          for packet in message.packets: await stream.mux(packet)
          stream.duration = Fraction(message.timestamp - start_time, 1000) # NOTE this should optimally happen before, how do we solve this?
        except ValidationError: pass

  async def run(self):
    try:
      container = None
      container = OutputContainer(self.config.destination, **self.config.container_options)
      tasks = [ *(asyncio.create_task(self._run_video(cfg, container)) for cfg in self.config.videos) ]
      # TODO add barrier here
      self.client.start()
      done, pending = await asyncio.wait(tasks, return_when="FIRST_COMPLETED")
      for t in pending: t.cancel()
      for t in done: await t 
    finally:
      if container is not None: await container.close()

class OutputContainerTaskHost(TaskHost):
  @property
  def metadata(self): return {
    **static_configurator(
      label="output container",
      inputs=[],
      default_config=OutputContainerConfig.default_config().model_dump(),
      editor_fields=[
        {
          "type": "text",
          "key": "destination",
          "label": "destination path or url",
        },
        MediaEditorFields.options("container_options"),
    ]),
    "js:configurator": "std:container",
    "cfg:isinput": False,
    "cfg:videoiomap": json.dumps({ v: v for v in [ "pixel_format", "codec", "width", "height", "rate" ] }),
    "cfg:videoeditorfields": json.dumps([
      MediaEditorFields.pixel_format(),
      MediaEditorFields.video_codec_name("w"),
      MediaEditorFields.pixel_size("width"),
      MediaEditorFields.pixel_size("height"),
      MediaEditorFields.frame_rate(),
      MediaEditorFields.options("codec_options"),
    ])
  }
  async def create_task(self, config: Any, topic_space_id: int | None):
    return OutputContainerTask(await self.create_client(topic_space_id), OutputContainerConfig.model_validate(config))
