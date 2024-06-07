from fractions import Fraction
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.debugging import ddebug_value
from streamtasks.env import DEBUG_MEDIA
from streamtasks.media.audio import AudioCodecInfo, AudioFrame
from streamtasks.net.serialization import RawData
from streamtasks.message.types import MediaMessage, TimestampChuckMessage
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class AudioEncoderConfigBase(BaseModel):
  in_sample_format: IOTypes.SampleFormat = "s16"
  out_sample_format: IOTypes.SampleFormat = "fltp"
  channels: IOTypes.Channels = 1
  encoder: IOTypes.CoderName = "aac"
  codec: IOTypes.CodecName = "aac"
  rate: IOTypes.SampleRate = 32000
  codec_options: dict[str, str] = {}

class AudioEncoderConfig(AudioEncoderConfigBase):
  out_topic: int
  in_topic: int

class AudioEncoderTask(Task):
  def __init__(self, client: Client, config: AudioEncoderConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config

    self.time_base = Fraction(1, config.rate)
    self.t0: int | None = None

    out_codec_info = AudioCodecInfo(codec=config.encoder, sample_rate=config.rate, sample_format=config.out_sample_format, channels=config.channels, options=config.codec_options)
    self.encoder = out_codec_info.get_encoder()

  async def run(self):
    try:
      async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
        self.client.start()
        while True:
          try:
            data = await self.in_topic.recv_data()
            message = TimestampChuckMessage.model_validate(data.data)
            if self.t0 is None: self.t0 = message.timestamp

            frame = AudioFrame.from_buffer(message.data, self.config.out_sample_format, self.config.channels, self.config.rate)
            frame.set_ts(Fraction(message.timestamp - self.t0, 1000), self.time_base)

            packets = await self.encoder.encode(frame)
            for packet in packets:
              if DEBUG_MEDIA(): ddebug_value("audio encoder time", float(packet.dts * self.time_base))
              await self.out_topic.send(RawData(MediaMessage(timestamp=int(self.t0 + packet.dts * self.time_base * 1000), packet=packet).model_dump()))
          except ValidationError: pass
    finally:
      self.encoder.close()

class AudioEncoderTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="audio encoder",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "content": "audio", "codec": "raw" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "audio" }],
    default_config=AudioEncoderConfigBase().model_dump(),
    config_to_input_map={ "in_topic": { **{ v: v for v in [ "rate", "channels" ] }, "in_sample_format": "sample_format" } },
    config_to_output_map=[ { **{ v: v for v in [ "rate", "channels", "codec" ] }, "out_sample_format": "sample_format" } ],
    editor_fields=[
      MediaEditorFields.sample_format("in_sample_format"),
      MediaEditorFields.sample_format("out_sample_format"),
      MediaEditorFields.audio_codec("w", coder_key="encoder"),
      MediaEditorFields.channel_count(),
      MediaEditorFields.sample_rate(),
      EditorFields.options("codec_options"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return AudioEncoderTask(await self.create_client(topic_space_id), AudioEncoderConfig.model_validate(config))
