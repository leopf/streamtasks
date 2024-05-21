from contextlib import AsyncExitStack
from typing import Any
from pydantic import BaseModel
from streamtasks.client.topic import SequentialInTopicSynchronizer
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
  synchronized: bool = True

class AudioMixerConfig(AudioMixerConfigBase):
  out_topic: int

class AudioMixerTask(Task):
  def __init__(self, client: Client, config: AudioMixerConfig):
    super().__init__(client)
    if config.synchronized:
      sync = SequentialInTopicSynchronizer()
      self.in_topics = [ self.client.sync_in_topic(track.in_topic, sync) for track in config.audio_tracks ]
    else:
      self.in_topics = [ self.client.in_topic(track.in_topic) for track in config.audio_tracks ]

    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config

  async def run(self):
    async with AsyncExitStack() as exit_stack:
      await exit_stack.enter_async_context(self.out_topic)
      await exit_stack.enter_async_context(self.out_topic.RegisterContext())

      for in_topic in self.in_topics:
        await exit_stack.enter_async_context(in_topic)
        await exit_stack.enter_async_context(in_topic.RegisterContext())

class AudioMixerTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="audio mixer",
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "audio", "codec": "raw" }],
    default_config=AudioMixerConfigBase().model_dump(),
    config_to_output_map=[ { v: v for v in [ "rate", "sample_format", "channels" ] } ],
    editor_fields=[
      MediaEditorFields.sample_format(),
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
