import asyncio
import json
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.media.audio import AudioCodecInfo
from streamtasks.media.container import InputContainer
from streamtasks.media.video import VideoCodecInfo
from streamtasks.net.message.data import MessagePackData
from streamtasks.system.configurators import IOTypes, static_configurator
from streamtasks.net.message.structures import MediaMessage
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.utils import get_timestamp_ms

class ContainerVideoInputConfigBase(BaseModel):
  pixel_format: IOTypes.PixelFormat
  codec: IOTypes.Codec
  width: IOTypes.Width
  height: IOTypes.Height
  rate: IOTypes.Rate
  force_transcode: bool
  codec_options: dict[str, str]
  
  @staticmethod
  def default_config(): return ContainerVideoInputConfigBase(pixel_format="yuv420p", codec="h264", width=1280, height=720, rate=30, force_transcode=False, codec_options={})

class ContainerVideoInputConfig(ContainerVideoInputConfigBase):
  out_topic: int

class ContainerAudioInputConfigBase(BaseModel):
  sample_format: IOTypes.SampleFormat
  codec: IOTypes.Codec
  channels: IOTypes.Channels
  rate: IOTypes.Rate
  force_transcode: bool
  codec_options: dict[str, str]
  
  @staticmethod
  def default_config(): return ContainerAudioInputConfigBase(codec="aac", sample_format="fltp", channels=1, rate=32000, force_transcode=False, codec_options={})

class ContainerAudioInputConfig(ContainerAudioInputConfigBase):
  out_topic: int

class InputContainerConfig(BaseModel):
  source: str
  videos: list[ContainerVideoInputConfig]
  audios: list[ContainerAudioInputConfig]
  container_options: dict[str, str]

  @staticmethod
  def default_config(): return InputContainerConfig(source="", container_options={}, audios=[], videos=[])

class InputContainerTask(Task):
  def __init__(self, client: Client, config: InputContainerConfig):
    super().__init__(client)
    self.config = config

  async def _run_video(self, index: int, config: ContainerVideoInputConfig, container: InputContainer):
    out_topic = self.client.out_topic(config.out_topic)
    codec_info = VideoCodecInfo(width=config.width, height=config.height, frame_rate=config.rate, pixel_format=config.pixel_format, codec=config.codec, options=config.codec_options)
    stream = container.get_video_stream(index, codec_info, config.force_transcode)
    async with out_topic, out_topic.RegisterContext():
      while True:
        packets = await stream.demux()
        if len(packets) > 0:
          assert all(p.rel_dts >= 0 for p in packets), "rel dts must be greater >= 0"
          await out_topic.send(MessagePackData(MediaMessage(timestamp=get_timestamp_ms(), packets=packets).model_dump()))
          
  async def _run_audio(self, index: int, config: ContainerAudioInputConfig, container: InputContainer):
    out_topic = self.client.out_topic(config.out_topic)
    codec_info = AudioCodecInfo(channels=config.channels, codec=config.codec, sample_rate=config.rate, sample_format=config.sample_format, options=config.codec_options)
    stream = container.get_audio_stream(index, codec_info, config.force_transcode)
    async with out_topic, out_topic.RegisterContext():
      while True:
        packets = await stream.demux()
        if len(packets) > 0:
          assert all(p.rel_dts >= 0 for p in packets), "rel dts must be greater >= 0"
          await out_topic.send(MessagePackData(MediaMessage(timestamp=get_timestamp_ms(), packets=packets).model_dump()))
          
  async def run(self):
    try:
      container = None
      container = await InputContainer.open(self.config.source, **self.config.container_options)
      tasks = [ 
        *(asyncio.create_task(self._run_video(idx, cfg, container)) for idx, cfg in enumerate(self.config.videos)),
        *(asyncio.create_task(self._run_audio(idx, cfg, container)) for idx, cfg in enumerate(self.config.audios)) 
      ]
      self.client.start()
      
      done, pending = await asyncio.wait(tasks, return_when="FIRST_COMPLETED")
      for t in pending: t.cancel()
      for t in done: await t 
    finally:
      if container is not None: await container.close()

class InputContainerTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="input container",
    default_config=InputContainerConfig.default_config().model_dump(),
    editor_fields=[
      {
        "type": "text",
        "key": "source",
        "label": "source path or url",
      },
      MediaEditorFields.options("container_options"),
    ]),
    "js:configurator": "std:container",
    "cfg:isinput": True,
    "cfg:videoiomap": json.dumps({ v: v for v in [ "pixel_format", "codec", "width", "height", "rate" ] }),
    "cfg:videoio": json.dumps({ "type": "ts", "content": "video" }),
    "cfg:videoconfig": json.dumps(ContainerVideoInputConfigBase.default_config().model_dump()),
    "cfg:videoeditorfields": json.dumps([
      MediaEditorFields.pixel_format(),
      MediaEditorFields.video_codec_name("w"),
      MediaEditorFields.pixel_size("width"),
      MediaEditorFields.pixel_size("height"),
      MediaEditorFields.frame_rate(),
      MediaEditorFields.boolean("force_transcode"),
      MediaEditorFields.options("codec_options"),
    ]),
    "cfg:audioiomap": json.dumps({ v: v for v in [ "codec", "rate", "channels", "sample_format" ] }),
    "cfg:audioio": json.dumps({ "type": "ts", "content": "audio" }),
    "cfg:audioconfig": json.dumps(ContainerAudioInputConfigBase.default_config().model_dump()),
    "cfg:audioeditorfields": json.dumps([
      MediaEditorFields.audio_codec_name("w"),
      MediaEditorFields.sample_format(),
      MediaEditorFields.sample_rate(),
      MediaEditorFields.channel_count(),
      MediaEditorFields.boolean("force_transcode"),
      MediaEditorFields.options("codec_options"),
    ])
  }
  async def create_task(self, config: Any, topic_space_id: int | None):
    return InputContainerTask(await self.create_client(topic_space_id), InputContainerConfig.model_validate(config))
