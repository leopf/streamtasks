import asyncio
from fractions import Fraction
import json
from typing import Any
from extra.debugging import ddebug_value
from pydantic import BaseModel, ValidationError
from streamtasks.client.topic import SequentialInTopicSynchronizer
from streamtasks.media.audio import AudioCodecInfo
from streamtasks.media.container import DEBUG_MEDIA, AVOutputStream, OutputContainer
from streamtasks.media.video import VideoCodecInfo
from streamtasks.system.configurators import EditorFields, IOTypes, multitrackio_configurator, static_configurator
from streamtasks.net.message.structures import MediaMessage
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.utils import AsyncTrigger

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
  video_tracks: list[ContainerVideoOutputConfig]
  audio_tracks: list[ContainerAudioOutputConfig]
  container_options: dict[str, str]

  @staticmethod
  def default_config(): return OutputContainerConfig(destination="", video_tracks=[], audio_tracks=[], container_options={})

class OutputContainerTask(Task):
  def __init__(self, client: Client, config: OutputContainerConfig):
    super().__init__(client)
    self.config = config
    self.sync = SequentialInTopicSynchronizer()
    self._packet_processed_trigger = AsyncTrigger()
    self._t0: int | None = None

  async def _run_stream(self, stream: AVOutputStream, in_topic_id: int):
    in_topic = self.client.sync_in_topic(in_topic_id, self.sync)
    async with in_topic, in_topic.RegisterContext():
      while True:
        try:
          data = await in_topic.recv_data()
          message = MediaMessage.model_validate(data.data)
          if DEBUG_MEDIA: ddebug_value("out", stream._stream.type, message.timestamp)
          if self._t0 is None: self._t0 = message.timestamp
          for packet in message.packets: await stream.mux(packet)
          assert all(p.rel_dts >= 0 for p in message.packets), "rel dts must be greater >= 0"
        except ValidationError: pass

  async def _run_syncer(self, streams: dict[int, AVOutputStream]):
    while True:
      await self.sync._timestamp_trigger.wait()
      if self._t0 is None: continue
      for tid, stream in streams.items():
        if tid in self.sync._topic_timestamps: # TODO pausing support
          stream.duration = Fraction(self.sync._topic_timestamps[tid] - self._t0, 1000)
          if DEBUG_MEDIA: ddebug_value("out stream dur.", stream._stream.type, (float(stream.duration), self.sync._topic_timestamps[tid]))

  async def run(self):
    try:
      container = None
      container = await OutputContainer.open(self.config.destination, **self.config.container_options)
      streams: dict[int, AVOutputStream] = {}
      streams.update({ cfg.in_topic: container.add_video_stream(cfg.to_codec_info()) for cfg in self.config.video_tracks })
      streams.update({ cfg.in_topic: container.add_audio_stream(cfg.to_codec_info()) for cfg in self.config.audio_tracks })
      tasks = [
        asyncio.create_task(self._run_syncer(streams)),
        *(asyncio.create_task(self._run_stream(stream, in_topic_id)) for in_topic_id, stream in streams.items()),
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
        EditorFields.text(key="destination", label="destination path or url"),
        EditorFields.options("container_options"),
    ]),
    **multitrackio_configurator(is_input=True, track_configs=[
      {
        "key": "video",
        "defaultConfig": ContainerVideoOutputConfigBase.default_config().model_dump(),
        "defaultIO": { "type": "ts", "content": "video" },
        "editorFields": [
          MediaEditorFields.pixel_format(),
          MediaEditorFields.video_codec_name("w"),
          MediaEditorFields.pixel_size("width"),
          MediaEditorFields.pixel_size("height"),
          MediaEditorFields.frame_rate(),
        ],
        "ioMap": { v: v for v in [ "pixel_format", "codec", "width", "height", "rate" ] },
      },
      {
        "key": "audio",
        "defaultConfig": ContainerAudioOutputConfigBase.default_config().model_dump(),
        "defaultIO": { "type": "ts", "content": "audio" },
        "editorFields": [
          MediaEditorFields.audio_codec_name("w"),
          MediaEditorFields.sample_format(),
          MediaEditorFields.sample_rate(),
          MediaEditorFields.channel_count()
        ],
        "ioMap": { v: v for v in [ "codec", "rate", "channels", "sample_format" ] },
      }
    ])
  }
  async def create_task(self, config: Any, topic_space_id: int | None):
    return OutputContainerTask(await self.create_client(topic_space_id), OutputContainerConfig.model_validate(config))
