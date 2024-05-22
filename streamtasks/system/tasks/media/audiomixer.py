import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass
from fractions import Fraction
from typing import Any
from jsonschema import ValidationError
import numpy as np
from pydantic import BaseModel, field_validator
from extra.debugging import ddebug_value
from streamtasks.client.topic import InTopic, SequentialInTopicSynchronizer
from streamtasks.media.audio import audio_buffer_to_ndarray
from streamtasks.media.util import AudioSequencer, list_sample_formats
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import TimestampChuckMessage
from streamtasks.net.message.types import TopicControlData
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.system.configurators import EditorFields, IOTypes, multitrackio_configurator, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class AudioTrackBase(BaseModel):
  label: str = "audio track"

class AudioTrack(AudioTrackBase):
  in_topic: int

class AudioMixerConfigBase(BaseModel):
  audio_tracks: list[AudioTrack] = []
  sample_format: IOTypes.SampleFormat = "s16"
  rate: IOTypes.SampleRate = 32000
  channels: IOTypes.Channels = 1
  max_desync: int = 100
  synchronized: bool = True

  @property
  def max_desync_time(self): return Fraction(self.max_desync, 1000)

  @field_validator("sample_format")
  @classmethod
  def validate_address_name(cls, value: str):
    if "p" in value: raise ValueError("Only non planar formats allowed!")
    return value

class AudioMixerConfig(AudioMixerConfigBase):
  out_topic: int

@dataclass
class AudioTrackContext:
  topic: InTopic
  sequencer: AudioSequencer
  is_paused: bool

class AudioMixerTask(Task):
  def __init__(self, client: Client, config: AudioMixerConfig):
    super().__init__(client)
    config.max_desync = 1
    if config.synchronized:
      sync = SequentialInTopicSynchronizer()
      in_topics = [ self.client.sync_in_topic(track.in_topic, sync) for track in config.audio_tracks ]
    else:
      in_topics = [ self.client.in_topic(track.in_topic) for track in config.audio_tracks ]

    self.audio_tracks = [ AudioTrackContext(topic=in_topic, sequencer=AudioSequencer(config.rate, config.max_desync_time), is_paused=False) for in_topic in in_topics ]
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config

  async def run(self):
    try:
      async with AsyncExitStack() as exit_stack:
        await exit_stack.enter_async_context(self.out_topic)
        await exit_stack.enter_async_context(self.out_topic.RegisterContext())

        for track in self.audio_tracks:
          await exit_stack.enter_async_context(track.topic)
          await exit_stack.enter_async_context(track.topic.RegisterContext())
        self.client.start()
        await asyncio.gather(*(self.run_track(track) for track in self.audio_tracks))
    except BaseException as e:
      import traceback
      print(traceback.format_exc())
      raise e

  async def run_track(self, track: AudioTrackContext):
    t0: None | int = None
    sample_count: int = 0
    while True:
      try:
        data = await track.topic.recv_data_control()
        if isinstance(data, TopicControlData):
          if track.is_paused and not data.paused: track.sequencer.reset(True) # hard reset on unpause
          track.is_paused = data.paused
          t0 = None
          sample_count = 0
        else:
          message = TimestampChuckMessage.model_validate(data.data)
          ddebug_value("track timestamp", id(track.sequencer), message.timestamp)
          samples = audio_buffer_to_ndarray(message.data, self.config.sample_format)[0].reshape((-1, self.config.channels))
          if t0 is None: t0 = message.timestamp - 1
          sample_count += samples.shape[0]
          ddebug_value("track sample rate", id(track.sequencer), sample_count * 1000 / (message.timestamp - t0))
          track.sequencer.insert(Fraction(message.timestamp, 1000), samples)
          await self.send_next()
      except ValidationError: pass

  async def send_next(self):
    if any(True for track in self.audio_tracks if not track.is_paused and not track.sequencer.started): return # not ready yet
    start_times = [track.sequencer.start_time for track in self.audio_tracks if not track.is_paused]
    if len(start_times) == 0: return
    start_times.sort()

    target_times = [ t for t in start_times if t - self.config.max_desync_time  < start_times[0] ]
    target_time = sum(target_times) / len(target_times)
    num_sample_counts = min(track.sequencer.get_max_samples(target_time) for track in self.audio_tracks if not track.is_paused)
    if num_sample_counts <= 0: return

    result: np.ndarray | None = None
    for track in self.audio_tracks:
      if track.sequencer.start_time:
        ddebug_value("track start", id(track.sequencer), track.sequencer.start_time)
        ddebug_value("track duration", id(track.sequencer), track.sequencer.get_max_samples(track.sequencer.start_time))
      if track.sequencer.started:
        new_samples = track.sequencer.pop_start(target_time, num_sample_counts)
        assert new_samples.shape[0] == num_sample_counts, "wrong amount of samples from sequencer!"
        if result is not None: result = result + new_samples
        else: result = new_samples
      if track.is_paused: track.sequencer.reset()

    if result.size != 0:
      await self.out_topic.send(MessagePackData(TimestampChuckMessage(timestamp=round(target_time * 1000), data=result.tobytes("C")).model_dump()))

class AudioMixerTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="audio mixer",
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "audio", "codec": "raw" }],
    default_config=AudioMixerConfigBase().model_dump(),
    config_to_output_map=[ { v: v for v in [ "rate", "sample_format", "channels" ] } ],
    editor_fields=[
      MediaEditorFields.sample_format(allowed_values=set(fmt for fmt in list_sample_formats() if "p" not in fmt)),
      MediaEditorFields.sample_rate(),
      MediaEditorFields.channel_count(),
      EditorFields.boolean(key="synchronized"),
    ]
  ),
  **multitrackio_configurator(is_input=True, track_configs=[{
    "key": "audio",
    "ioMap": { "label": "label" },
    "defaultConfig": AudioTrackBase().model_dump(),
    "editorFields": [ EditorFields.text("label") ],
    "defaultIO": { "type": "ts", "content": "audio", "codec": "raw" },
    "globalIOMap": { v: v for v in [ "rate", "channels", "sample_format" ] },
  }])}
  async def create_task(self, config: Any, topic_space_id: int | None):
    return AudioMixerTask(await self.create_client(topic_space_id), AudioMixerConfig.model_validate(config))
