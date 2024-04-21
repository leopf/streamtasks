import asyncio
from fractions import Fraction
import json
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.client.topic import SequentialInTopicSynchronizer
from streamtasks.media.audio import AudioCodecInfo
from streamtasks.media.container import AVOutputStream, OutputContainer
from streamtasks.media.video import VideoCodecInfo
from streamtasks.system.configurators import IOTypes, static_configurator
from streamtasks.net.message.structures import MediaMessage
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from streamtasks.system.tasks.media.utils import MediaEditorFields

class ContainerVideoOutputConfigBase(BaseModel):
  pixel_format: IOTypes.PixelFormat
  codec: IOTypes.Codec
  width: IOTypes.Width
  height: IOTypes.Height
  rate: IOTypes.Rate
  
  def to_codec_info(self): return VideoCodecInfo(width=self.width, height=self.height, frame_rate=self.rate, pixel_format=self.pixel_format, codec=self.codec)
  
  @staticmethod
  def default_config(): return ContainerVideoOutputConfigBase(pixel_format="yuv420p", codec="h264", width=1280, height=720, rate=30)

class ContainerVideoOutputConfig(ContainerVideoOutputConfigBase):
  in_topic: int

class ContainerAudioOutputConfigBase(BaseModel):
  sample_format: IOTypes.SampleFormat
  codec: IOTypes.Codec
  channels: IOTypes.Channels
  rate: IOTypes.Rate
  
  def to_codec_info(self): return AudioCodecInfo(codec=self.codec, channels=self.channels, sample_rate=self.rate, sample_format=self.sample_format)
  
  @staticmethod
  def default_config(): return ContainerAudioOutputConfigBase(codec="aac", sample_format="fltp", channels=1, rate=32000)

class ContainerAudioOutputConfig(ContainerAudioOutputConfigBase):
  in_topic: int

class OutputContainerConfig(BaseModel):
  destination: str
  videos: list[ContainerVideoOutputConfig]
  audios: list[ContainerAudioOutputConfig]
  container_options: dict[str, str]

  @staticmethod
  def default_config(): return OutputContainerConfig(destination="", videos=[], audios=[], container_options={})

class OutputContainerTask(Task):
  def __init__(self, client: Client, config: OutputContainerConfig):
    super().__init__(client)
    self.config = config
    self.sync = SequentialInTopicSynchronizer()

  async def _run_stream(self, stream: AVOutputStream, in_topic_id: int):
    in_topic = self.client.sync_in_topic(in_topic_id, self.sync)
    start_time: int | None = None
    async with in_topic, in_topic.RegisterContext():
      while True:
        try:
          data = await in_topic.recv_data()
          message = MediaMessage.model_validate(data.data)
          # print(stream._stream.type, message.timestamp)
          start_time = start_time or message.timestamp
          if start_time == message.timestamp: print("start time ", stream._stream.type, start_time)
          for packet in message.packets: await stream.mux(packet)
          assert all(p.rel_dts >= 0 for p in message.packets), "rel dts must be greater >= 0"
          stream.duration = Fraction(message.timestamp - start_time, 1000) # NOTE this should optimally happen before, how do we solve this?
        except ValidationError: pass

  async def run(self):
    try:
      container = None
      container = await OutputContainer.open(self.config.destination, **self.config.container_options)
      tasks = [ 
        *(asyncio.create_task(self._run_stream(container.add_video_stream(cfg.to_codec_info()), cfg.in_topic)) for cfg in self.config.videos),
        *(asyncio.create_task(self._run_stream(container.add_audio_stream(cfg.to_codec_info()), cfg.in_topic)) for cfg in self.config.audios),
      ]
      # TODO add barrier here
      self.client.start()
      done, pending = await asyncio.wait(tasks, return_when="FIRST_EXCEPTION")
      for t in pending: t.cancel()
      for t in done: await t 
    except asyncio.CancelledError: pass
    finally:
      if container is not None: await container.close()

class OutputContainerTaskHost(TaskHost):
  @property
  def metadata(self): return {
    **static_configurator(
      label="output container",
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
    "cfg:videoio": json.dumps({ "type": "ts", "content": "video" }),
    "cfg:videoconfig": json.dumps(ContainerVideoOutputConfigBase.default_config().model_dump()),
    "cfg:videoeditorfields": json.dumps([
      MediaEditorFields.pixel_format(),
      MediaEditorFields.video_codec_name("w"),
      MediaEditorFields.pixel_size("width"),
      MediaEditorFields.pixel_size("height"),
      MediaEditorFields.frame_rate(),
    ]),
    "cfg:audioiomap": json.dumps({ v: v for v in [ "codec", "rate", "channels", "sample_format" ] }),
    "cfg:audioio": json.dumps({ "type": "ts", "content": "audio" }),
    "cfg:audioconfig": json.dumps(ContainerAudioOutputConfigBase.default_config().model_dump()),
    "cfg:audioeditorfields": json.dumps([
      MediaEditorFields.audio_codec_name("w"),
      MediaEditorFields.sample_format(),
      MediaEditorFields.sample_rate(),
      MediaEditorFields.channel_count(),
    ])
  }
  async def create_task(self, config: Any, topic_space_id: int | None):
    return OutputContainerTask(await self.create_client(topic_space_id), OutputContainerConfig.model_validate(config))
