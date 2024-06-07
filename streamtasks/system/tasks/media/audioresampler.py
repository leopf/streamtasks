from fractions import Fraction
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.media.audio import AudioFrame, AudioResampler, AudioResamplerInfo
from streamtasks.net.serialization import RawData
from streamtasks.message.types import TimestampChuckMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.system.configurators import IOTypes, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class AudioResamplerConfigBase(BaseModel):
  in_sample_format: IOTypes.SampleFormat = "s16"
  in_rate: IOTypes.SampleRate = 32000
  in_channels: IOTypes.Channels = 1

  out_sample_format: IOTypes.SampleFormat = "s16"
  out_rate: IOTypes.SampleRate = 32000
  out_channels: IOTypes.Channels = 1

class AudioResamplerConfig(AudioResamplerConfigBase):
  out_topic: int
  in_topic: int

class AudioResamplerTask(Task):
  def __init__(self, client: Client, config: AudioResamplerConfig):
    super().__init__(client)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.resampler = AudioResampler(
      AudioResamplerInfo(self.config.out_sample_format, self.config.out_channels, self.config.out_rate),
      AudioResamplerInfo(self.config.in_sample_format, self.config.in_channels, self.config.in_rate)
    )

  async def run(self):
    t0: int | None = None
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      while True:
        try:
          data = await self.in_topic.recv_data_control()
          if isinstance(data, TopicControlData): await self.out_topic.set_paused(data.paused)
          else:
            message = TimestampChuckMessage.model_validate(data.data)
            if t0 is None: t0 = message.timestamp
            frame = AudioFrame.from_buffer(message.data, self.config.in_sample_format, self.config.in_channels, self.config.in_rate)
            frame.set_ts(Fraction(message.timestamp - t0, 1000), Fraction(1, self.config.in_rate))
            for nframe in await self.resampler.reformat(frame):
              await self.out_topic.send(RawData(TimestampChuckMessage(timestamp=int(nframe.dtime * 1000) + t0, data=nframe.to_bytes()).model_dump()))
        except (ValidationError, ValueError): pass

class AudioResamplerTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="audio resampler",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "content": "audio", "codec": "raw" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "audio", "codec": "raw" }],
    default_config=AudioResamplerConfigBase().model_dump(),
    config_to_input_map={ "in_topic": { f"in_{v}": v for v in [ "rate", "sample_format", "channels" ] } },
    config_to_output_map=[ { f"out_{v}": v for v in [ "rate", "sample_format", "channels" ] } ],
    editor_fields=[
      MediaEditorFields.sample_format(key="in_sample_format", label="input sample format"),
      MediaEditorFields.sample_rate(key="in_rate", label="input sample rate"),
      MediaEditorFields.channel_count(key="in_channels", label="input channels"),
      MediaEditorFields.sample_format(key="out_sample_format", label="output sample format"),
      MediaEditorFields.sample_rate(key="out_rate", label="output sample rate"),
      MediaEditorFields.channel_count(key="out_channels", label="output channels"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return AudioResamplerTask(await self.create_client(topic_space_id), AudioResamplerConfig.model_validate(config))
