import asyncio
from fractions import Fraction
from typing import Any
from extra.debugging import ddebug_value
from pydantic import BaseModel
from streamtasks.env import DEBUG_MEDIA
from streamtasks.media.audio import AudioCodecInfo
from streamtasks.media.container import AVInputStream, InputContainer
from streamtasks.media.video import VideoCodecInfo
from streamtasks.net.message.data import MessagePackData
from streamtasks.system.configurators import EditorFields, IOTypes, multitrackio_configurator, static_configurator
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
  rate: IOTypes.FrameRate
  force_transcode: bool
  codec_options: dict[str, str]

  def to_codec_info(self): return VideoCodecInfo(width=self.width, height=self.height, frame_rate=self.rate, pixel_format=self.pixel_format, codec=self.codec, options=self.codec_options)

  @staticmethod
  def default_config(): return ContainerVideoInputConfigBase(pixel_format="yuv420p", codec="h264", width=1280, height=720, rate=30, force_transcode=False, codec_options={})

class ContainerVideoInputConfig(ContainerVideoInputConfigBase):
  out_topic: int

class ContainerAudioInputConfigBase(BaseModel):
  sample_format: IOTypes.SampleFormat
  codec: IOTypes.Codec
  channels: IOTypes.Channels
  rate: IOTypes.SampleRate
  force_transcode: bool
  codec_options: dict[str, str]

  def to_codec_info(self): return AudioCodecInfo(codec=self.codec, channels=self.channels, sample_rate=self.rate, sample_format=self.sample_format, options=self.codec_options)

  @staticmethod
  def default_config(): return ContainerAudioInputConfigBase(codec="aac", sample_format="fltp", channels=1, rate=32000, force_transcode=False, codec_options={})

class ContainerAudioInputConfig(ContainerAudioInputConfigBase):
  out_topic: int

class InputContainerConfig(BaseModel):
  source: str
  video_tracks: list[ContainerVideoInputConfig]
  audio_tracks: list[ContainerAudioInputConfig]
  container_options: dict[str, str]

  @staticmethod
  def default_config(): return InputContainerConfig(source="", container_options={}, audio_tracks=[], video_tracks=[])

class InputContainerTask(Task):
  def __init__(self, client: Client, config: InputContainerConfig):
    super().__init__(client)
    self.config = config
    self._t0: int | None = None

  async def _run_stream(self, stream: AVInputStream, out_topic_id: int):
    try:
      out_topic = self.client.out_topic(out_topic_id)
      async with out_topic, out_topic.RegisterContext():
        while True:
          packets = await stream.demux()
          assert all(p.rel_dts >= 0 for p in packets), "rel dts must be greater >= 0"
          for packet in packets:
            assert packet.dts is not None
            ts = stream.convert_position(packet.dts or 0, Fraction(1, 1000))
            if self._t0 is None: self._t0 = get_timestamp_ms() - ts
            if DEBUG_MEDIA(): ddebug_value("in", stream._stream.type, ts)
            await out_topic.send(MessagePackData(MediaMessage(timestamp=self._t0 + ts, packet=packet).model_dump()))
    except EOFError: pass
  async def run(self):
    try:
      container: InputContainer | None = None
      tasks: list[asyncio.Task] = []
      container = await InputContainer.open(self.config.source, **self.config.container_options)
      tasks = [
        *(asyncio.create_task(self._run_stream(container.get_video_stream(idx, cfg.to_codec_info(), cfg.force_transcode), cfg.out_topic)) for idx, cfg in enumerate(self.config.video_tracks)),
        *(asyncio.create_task(self._run_stream(container.get_audio_stream(idx, cfg.to_codec_info(), cfg.force_transcode), cfg.out_topic)) for idx, cfg in enumerate(self.config.audio_tracks)),
      ]
      self.client.start()
      done, _ = await asyncio.wait(tasks, return_when="FIRST_EXCEPTION")
      for t in done: await t
    except asyncio.CancelledError: pass
    finally:
      if container is not None: await container.close()
      for t in tasks:
        try:
          t.cancel()
          await t
        except asyncio.CancelledError: pass

class InputContainerTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="input container",
    default_config=InputContainerConfig.default_config().model_dump(),
    editor_fields=[
      EditorFields.text(key="source", label="source path or url"),
      EditorFields.options("container_options"),
    ]),
    **multitrackio_configurator(is_input=False, track_configs=[
      {
        "defaultConfig": ContainerVideoInputConfigBase.default_config().model_dump(),
        "defaultIO": { "type": "ts", "content": "video" },
        "ioMap": { v: v for v in [ "pixel_format", "codec", "width", "height", "rate" ] },
        "key": "video",
        "editorFields": [
          MediaEditorFields.pixel_format(),
          MediaEditorFields.video_codec_name("w"),
          MediaEditorFields.pixel_size("width"),
          MediaEditorFields.pixel_size("height"),
          MediaEditorFields.frame_rate(),
          EditorFields.boolean("force_transcode"),
          EditorFields.options("codec_options"),
        ]
      },
      {
        "defaultConfig": ContainerAudioInputConfigBase.default_config().model_dump(),
        "defaultIO": { "type": "ts", "content": "audio" },
        "ioMap": { v: v for v in [ "codec", "rate", "channels", "sample_format" ] },
        "key": "audio",
        "editorFields": [
          MediaEditorFields.audio_codec_name("w"),
          MediaEditorFields.sample_format(),
          MediaEditorFields.sample_rate(),
          MediaEditorFields.channel_count(),
          EditorFields.boolean("force_transcode"),
          EditorFields.options("codec_options"),
        ]
      }
    ])
  }
  async def create_task(self, config: Any, topic_space_id: int | None):
    return InputContainerTask(await self.create_client(topic_space_id), InputContainerConfig.model_validate(config))
