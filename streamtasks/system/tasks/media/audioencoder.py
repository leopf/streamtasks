from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.media.audio import AudioCodecInfo, AudioFrame
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import MediaMessage, TimestampChuckMessage
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
import numpy as np

class AudioEncoderConfigBase(BaseModel):
  in_sample_format: IOTypes.SampleFormat = "fltp"
  out_sample_format: IOTypes.SampleFormat = "s16"
  channels: IOTypes.Channels = 1
  codec: IOTypes.Codec = "aac"
  rate: IOTypes.Rate = 32000
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

    in_codec_info = AudioCodecInfo(codec=config.codec, sample_rate=config.rate, sample_format=config.in_sample_format, channels=config.channels, options=config.codec_options)
    self.resampler = in_codec_info.get_resampler()
    out_codec_info = AudioCodecInfo(codec=config.codec, sample_rate=config.rate, sample_format=config.out_sample_format, channels=config.channels, options=config.codec_options)
    self.encoder = out_codec_info.get_encoder()

  async def run(self):
    try:
      async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
        self.client.start()
        while True:
          try:
            data = await self.in_topic.recv_data()
            message = TimestampChuckMessage.model_validate(data.data)
            bm = np.frombuffer(message.data, dtype=np.uint8) # TODO: endianness
            bm = bm.reshape((self.config.channels, -1))
            frame = AudioFrame.from_ndarray(bm, self.config.in_sample_format, self.config.channels, self.config.rate)
            packets = [p for p in await self.encoder.encode(frame) if p.dts is not None and p.pts is not None]
            if len(packets) > 0:
              await self.out_topic.send(MessagePackData(MediaMessage(timestamp=message.timestamp, packets=packets).model_dump()))
          except ValidationError: pass
    finally:
      self.encoder.close()
    
class AudioEncoderTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="audio encoder",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "content": "audio", "codec": "raw" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "audio" }],
    default_config=AudioEncoderConfigBase().model_dump(),
    config_to_input_map={ "in_topic": { **{ v: v for v in [ "rate", "channels" ] }, "in_sample_format": "sample_format" } },
    config_to_output_map=[ { **{ v: v for v in [ "rate", "channels", "codec" ] }, "out_sample_format": "sample_format" } ],
    editor_fields=[
      MediaEditorFields.sample_format("in_sample_format"),
      MediaEditorFields.sample_format("out_sample_format"),
      MediaEditorFields.audio_codec_name("r"),
      MediaEditorFields.channel_count(),
      MediaEditorFields.sample_rate(),
      EditorFields.options("codec_options"),
    ]
  )}
  async def create_task(self, config: Any, topic_space_id: int | None):
    return AudioEncoderTask(await self.create_client(topic_space_id), AudioEncoderConfig.model_validate(config))
  