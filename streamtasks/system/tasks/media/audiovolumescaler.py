import asyncio
from contextlib import AsyncExitStack
from typing import Any
import numpy as np
from pydantic import BaseModel, ValidationError
from streamtasks.client.topic import SequentialInTopicSynchronizer
from streamtasks.media.audio import audio_buffer_to_samples, sample_format_to_dtype
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import NumberMessage, TimestampChuckMessage
from streamtasks.net.message.types import TopicControlData
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class AudioVolumeScalerConfigBase(BaseModel):
  sample_format: IOTypes.SampleFormat = "s16"
  rate: IOTypes.SampleRate = 32000
  channels: IOTypes.Channels = 1
  default_scale: float = 1
  synchronized: bool = True

class AudioVolumeScalerConfig(AudioVolumeScalerConfigBase):
  out_topic: int
  in_topic: int
  scale_topic: int | None = None

class AudioVolumeScalerTask(Task):
  def __init__(self, client: Client, config: AudioVolumeScalerConfig):
    super().__init__(client)
    if config.synchronized:
      sync = SequentialInTopicSynchronizer()
      self.in_topic = self.client.sync_in_topic(config.in_topic, sync)
      self.scale_topic = None if config.scale_topic is None else self.client.sync_in_topic(config.scale_topic, sync)
    else:
      self.in_topic = self.client.in_topic(config.in_topic)
      self.scale_topic = None if config.scale_topic is None else self.client.in_topic(config.scale_topic)

    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.scale = config.default_scale

  async def run(self):
    async with AsyncExitStack() as exit_stack:
      await exit_stack.enter_async_context(self.out_topic)
      await exit_stack.enter_async_context(self.out_topic.RegisterContext())
      await exit_stack.enter_async_context(self.in_topic)
      await exit_stack.enter_async_context(self.in_topic.RegisterContext())
      if self.scale_topic is not None:
        await exit_stack.enter_async_context(self.scale_topic)
        await exit_stack.enter_async_context(self.scale_topic.RegisterContext())

      self.client.start()
      if self.scale_topic is not None: await asyncio.gather(self.run_in_audio(), self.run_in_scale())
      else: await self.run_in_audio()

  async def run_in_audio(self):
    samples_dtype = sample_format_to_dtype(self.config.sample_format)
    samples_dtype_info = np.iinfo(samples_dtype)
    while True:
      try:
        data = await self.in_topic.recv_data_control()
        if isinstance(data, TopicControlData): await self.out_topic.set_paused(data.paused)
        else:
          message = TimestampChuckMessage.model_validate(data.data)
          samples = audio_buffer_to_samples(message.data, sample_format=self.config.sample_format, channels=self.config.channels)
          samples = np.clip(samples * self.scale, samples_dtype_info.min, samples_dtype_info.max).astype(samples_dtype)
          await self.out_topic.send(MessagePackData(TimestampChuckMessage(timestamp=message.timestamp, data=samples.tobytes("C")).model_dump()))
      except (ValidationError, ValueError): pass

  async def run_in_scale(self):
    while True:
      try:
        data = await self.scale_topic.recv_data_control()
        if isinstance(data, TopicControlData):
          if data.paused: self.scale = self.config.default_scale
        else:
          message = NumberMessage.model_validate(data.data)
          self.scale = message.value
      except ValidationError: self.scale = self.config.default_scale

class AudioVolumeScalerTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="audio volume scaler",
    inputs=[
      { "label": "input", "type": "ts", "key": "in_topic", "content": "audio", "codec": "raw" },
      { "label": "scale", "type": "ts", "key": "scale_topic", "content": "number" }
    ],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "audio", "codec": "raw" }],
    default_config=AudioVolumeScalerConfigBase().model_dump(),
    config_to_input_map={ "in_topic": { v: v for v in [ "rate", "sample_format", "channels" ] } },
    config_to_output_map=[ { v: v for v in [ "rate", "sample_format", "channels" ] } ],
    editor_fields=[
      MediaEditorFields.sample_format(),
      MediaEditorFields.sample_rate(),
      MediaEditorFields.channel_count(),
      EditorFields.number(key="default_scale"),
      EditorFields.boolean(key="synchronized"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return AudioVolumeScalerTask(await self.create_client(topic_space_id), AudioVolumeScalerConfig.model_validate(config))