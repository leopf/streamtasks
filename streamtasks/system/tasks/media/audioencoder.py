from contextlib import asynccontextmanager
from fractions import Fraction
import queue
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.media.audio import AudioCodecInfo, AudioFrame
from streamtasks.net.serialization import RawData
from streamtasks.message.types import TimestampChuckMessage
from streamtasks.media.packet import MediaMessage
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client
from streamtasks.utils import context_task, hertz_to_fintervall

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

class AudioEncoderTask(SyncTask):
  def __init__(self, client: Client, config: AudioEncoderConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config

    self.time_base = hertz_to_fintervall(config.rate)
    self.t0: int | None = None

    codec_info = AudioCodecInfo(codec=config.encoder, sample_rate=config.rate, sample_format=config.out_sample_format, channels=config.channels, options=config.codec_options)
    self.encoder = codec_info.get_encoder()

    self.frame_data_queue: queue.Queue[TimestampChuckMessage] = queue.Queue()

  @asynccontextmanager
  async def init(self):
    try:
      async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext(), context_task(self._run_receiver()):
        self.client.start()
        yield
    finally:
      self.encoder.close()

  async def _run_receiver(self):
    while True:
      try:
        data = await self.in_topic.recv_data()
        self.frame_data_queue.put(TimestampChuckMessage.model_validate(data.data))
      except ValidationError: pass

  def run_sync(self):
    timeout = 0.5
    while not self.stop_event.is_set():
      try:
        message = self.frame_data_queue.get(timeout=timeout)
        if self.t0 is None: self.t0 = message.timestamp
        frame = AudioFrame.from_buffer(message.data, self.config.in_sample_format, self.config.channels, self.config.rate)
        frame.set_ts(Fraction(message.timestamp - self.t0, 1000), self.time_base)
        packets = self.encoder.encode_sync(frame)
        for packet in packets:
          self.send_data(self.out_topic, RawData(MediaMessage(timestamp=int(self.t0 + packet.dts * self.time_base * 1000), packet=packet).model_dump()))
        self.frame_data_queue.task_done()
      except queue.Empty: pass

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
