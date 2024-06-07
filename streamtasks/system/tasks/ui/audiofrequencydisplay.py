from contextlib import AsyncExitStack
import math
from typing import Any
import numpy as np
from pydantic import BaseModel, ValidationError
from streamtasks.media.audio import audio_buffer_to_ndarray
from streamtasks.media.util import AudioChunker
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.system.tasks.ui.controlbase import UIBaseTask, UIControlBaseTaskConfig
from streamtasks.message.types import TimestampChuckMessage
from streamtasks.system.task import TaskHost
from streamtasks.client import Client

class AudioFrequencyDisplayConfigBase(UIControlBaseTaskConfig):
  rate: IOTypes.SampleRate = 32000
  sample_format: IOTypes.SampleFormat = "s16"
  bin_size: int = 100

class AudioFrequencyDisplayConfig(AudioFrequencyDisplayConfigBase):
  in_topic: int

class AudioFrequencyDisplayValue(BaseModel):
  freq_bins: list[float]

class AudioFrequencyDisplayTask(UIBaseTask[AudioFrequencyDisplayConfig, AudioFrequencyDisplayValue]):
  def __init__(self, client: Client, config: AudioFrequencyDisplayConfig):
    super().__init__(client, config, AudioFrequencyDisplayValue(freq_bins=[]), "audio-frequency-display.js")
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config

  async def context(self):
    exit_stack = AsyncExitStack()
    await exit_stack.enter_async_context(self.in_topic)
    await exit_stack.enter_async_context(self.in_topic.RegisterContext())
    return exit_stack

  async def run_other(self):
    chunker = AudioChunker(self.config.rate, self.config.rate)
    while True:
      try:
        data = await self.in_topic.recv_data()
        message = TimestampChuckMessage.model_validate(data.data)
        new_samples = audio_buffer_to_ndarray(message.data, self.config.sample_format)[0]
        for chunk, _ in chunker.next(new_samples, 0):
          freqs = np.abs(np.fft.fft(chunk)[:chunk.size // 2])
          expected_len = math.ceil(freqs.size / self.config.bin_size) * self.config.bin_size
          freq_bins = np.pad(freqs, (expected_len - freqs.size)).reshape((-1, self.config.bin_size)).sum(-1)
          freq_bins = freq_bins / freq_bins.max()
          self.value = AudioFrequencyDisplayValue(freq_bins=list(freq_bins))
      except ValidationError: pass

class AudioFrequencyDisplayTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="Audio Frequency Display",
    inputs=[{ "label": "value", "key": "in_topic", "type": "ts", "content": "audio", "channels": 1, "codec": "raw" }],
    config_to_input_map={ "in_topic": { v: v for v in [ "rate", "sample_format" ] } },
    default_config=AudioFrequencyDisplayConfigBase().model_dump(),
    editor_fields=[
      MediaEditorFields.sample_format(),
      MediaEditorFields.sample_rate(),
      EditorFields.integer(key="bin_size", min_value=1)
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return AudioFrequencyDisplayTask(await self.create_client(topic_space_id), AudioFrequencyDisplayConfig.model_validate(config))
