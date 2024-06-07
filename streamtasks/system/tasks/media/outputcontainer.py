import asyncio
from fractions import Fraction
from typing import Any
from streamtasks.debugging import ddebug_value
from pydantic import BaseModel, ValidationError
from streamtasks.client.topic import InTopicSynchronizer
from streamtasks.env import DEBUG_MEDIA
from streamtasks.media.audio import AudioCodecInfo
from streamtasks.media.container import AVOutputStream, OutputContainer
from streamtasks.media.video import VideoCodecInfo
from streamtasks.system.configurators import EditorFields, IOTypes, multitrackio_configurator, static_configurator
from streamtasks.message.types import MediaMessage
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.utils import AsyncTrigger

class ContainerVideoOutputConfigBase(BaseModel):
  pixel_format: IOTypes.PixelFormat = "yuv420p"
  encoder: IOTypes.CoderName = "h264"
  codec: IOTypes.CodecName = "h264"
  width: IOTypes.Width = 1280
  height: IOTypes.Height = 720
  rate: IOTypes.FrameRate = 30

  def to_codec_info(self): return VideoCodecInfo(width=self.width, height=self.height, frame_rate=self.rate, pixel_format=self.pixel_format, codec=self.encoder)

class ContainerVideoOutputConfig(ContainerVideoOutputConfigBase):
  in_topic: int

class ContainerAudioOutputConfigBase(BaseModel):
  sample_format: IOTypes.SampleFormat = "fltp"
  encoder: IOTypes.CoderName = "aac"
  codec: IOTypes.CodecName = "aac"
  channels: IOTypes.Channels = 1
  rate: IOTypes.SampleRate = 32000

  def to_codec_info(self): return AudioCodecInfo(codec=self.encoder, channels=self.channels, sample_rate=self.rate, sample_format=self.sample_format)

class ContainerAudioOutputConfig(ContainerAudioOutputConfigBase):
  in_topic: int

class OutputContainerConfig(BaseModel):
  destination: str = ""
  video_tracks: list[ContainerVideoOutputConfig] = []
  audio_tracks: list[ContainerAudioOutputConfig] = []
  max_desync: int = 100
  container_options: dict[str, str] = {}

class OutputContainerSynchronizer(InTopicSynchronizer):
  def __init__(self, streams: dict[int, AVOutputStream], max_desync: int) -> None:
    super().__init__()
    self._streams = streams
    self.topic_timestamps: dict[int, int] = {}
    self._timestamp_trigger = AsyncTrigger()
    self._topic_return: bool = True
    self._t0: None | int = None
    self._startup_barrier = asyncio.Barrier(len(streams))
    self._oc_dropped_packets = 0
    self._max_desync = max_desync

  @property
  def min_timestamp(self): return 0 if len(self.topic_timestamps) == 0 else min(self.topic_timestamps.values())

  @property
  def min_duration(self): return min((stream.duration for tid, stream in self._streams.items() if tid in self.topic_timestamps))

  async def wait_for(self, topic_id: int, timestamp: int) -> bool:
    if timestamp < self.topic_timestamps.get(topic_id, 0) or topic_id not in self._streams: return False
    self._set_topic_timestamp(topic_id, timestamp)
    if self._t0 is None:
      await self._startup_barrier.wait()
      if self._t0 is None: self._t0 = self.min_timestamp

    duration = Fraction(timestamp - self._t0, 1000)
    stream = self._streams[topic_id]
    stream.duration = duration
    if DEBUG_MEDIA(): ddebug_value("stream dur.", stream._stream.type, (float(stream.duration), float(duration), (timestamp - self._t0) / 1000))
    drop = False
    while True:
      min_duration = self.min_duration
      min_timestamp = self.min_timestamp
      if stream.duration == min_duration and (timestamp - self._max_desync) <= min_timestamp:
        break # True
      if timestamp == min_timestamp and stream.duration != min_duration:
        next_min = self._get_next_min_duration_timestamp()
        if next_min - self._max_desync > timestamp:
          drop = True
          break
      await self._timestamp_trigger.wait()

    for other_topic_id, other_stream in self._streams.items():
      if other_topic_id not in self.topic_timestamps:
        other_stream.duration = duration

    if DEBUG_MEDIA() and drop:
      self._oc_dropped_packets += 1
      ddebug_value("output container dropped", self._oc_dropped_packets)
    return not drop

  async def set_paused(self, topic_id: int, paused: bool):
    if paused: self._set_topic_timestamp(topic_id, None)
    else: self._set_topic_timestamp(topic_id, self.min_timestamp)

  def _get_next_min_duration_timestamp(self):
    min_duration = self.min_duration
    return min((self.topic_timestamps[tid] for tid, stream in self._streams.items() if stream.duration == min_duration and tid in self.topic_timestamps))

  def _set_topic_timestamp(self, topic_id: int, timestamp: int | None):
    if timestamp is None: self.topic_timestamps.pop(topic_id, None)
    else: self.topic_timestamps[topic_id] = timestamp
    self._timestamp_trigger.trigger()

class OutputContainerTask(Task):
  def __init__(self, client: Client, config: OutputContainerConfig):
    super().__init__(client)
    self.config = config
    self.sync: OutputContainerSynchronizer
    self._packet_processed_trigger = AsyncTrigger()
    self._t0: int | None = None

  async def _run_stream(self, stream: AVOutputStream, in_topic_id: int):
    in_topic = self.client.sync_in_topic(in_topic_id, self.sync)
    async with in_topic, in_topic.RegisterContext():
      while True:
        try:
          data = await in_topic.recv_data()
          message = MediaMessage.model_validate(data.data)
          if DEBUG_MEDIA(): ddebug_value("out", stream._stream.type, message.timestamp)
          if self._t0 is None: self._t0 = message.timestamp
          await stream.mux(message.packet)
          assert message.packet.rel_dts >= 0, "rel dts must be greater >= 0"
        except ValidationError: pass

  async def run(self):
    try:
      container = None
      container = await OutputContainer.open(self.config.destination, **self.config.container_options)
      streams: dict[int, AVOutputStream] = {}
      streams.update({ cfg.in_topic: container.add_video_stream(cfg.to_codec_info()) for cfg in self.config.video_tracks })
      streams.update({ cfg.in_topic: container.add_audio_stream(cfg.to_codec_info()) for cfg in self.config.audio_tracks })
      self.sync = OutputContainerSynchronizer(streams, self.config.max_desync)
      tasks = [ asyncio.create_task(self._run_stream(stream, in_topic_id)) for in_topic_id, stream in streams.items() ]
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
      default_config=OutputContainerConfig().model_dump(),
      editor_fields=[
        EditorFields.text(key="destination", label="destination path or url"),
        EditorFields.integer(key="max_desync", label="maximum desynchronization", min_value=0, unit="ms"),
        EditorFields.options("container_options"),
    ]),
    **multitrackio_configurator(is_input=True, track_configs=[
      {
        "key": "video",
        "defaultConfig": ContainerVideoOutputConfigBase().model_dump(),
        "defaultIO": { "type": "ts", "content": "video" },
        "editorFields": [
          MediaEditorFields.pixel_format(),
          MediaEditorFields.video_codec("w", coder_key="encoder"),
          MediaEditorFields.pixel_size("width"),
          MediaEditorFields.pixel_size("height"),
          MediaEditorFields.frame_rate(),
        ],
        "ioMap": { v: v for v in [ "pixel_format", "codec", "width", "height", "rate" ] },
      },
      {
        "key": "audio",
        "defaultConfig": ContainerAudioOutputConfigBase().model_dump(),
        "defaultIO": { "type": "ts", "content": "audio" },
        "editorFields": [
          MediaEditorFields.audio_codec("w", coder_key="encoder"),
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
