from contextlib import asynccontextmanager
from typing import Any
from pydantic import BaseModel
from streamtasks.media.audio import get_audio_bytes_per_time_sample
from streamtasks.net.serialization import RawData
from streamtasks.message.types import TimestampChuckMessage
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client
from streamtasks.system.tasks.media.pa_utils import SAMPLE_FORMAT_2_PA_TYPE
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.utils import get_timestamp_ms
import pyaudio

class AudioInputConfigBase(BaseModel):
  sample_format: IOTypes.SampleFormat = "s16"
  channels: IOTypes.Channels = 1
  rate: IOTypes.SampleRate = 32000
  input_id: int = -1
  buffer_size: int = 1024

class AudioInputConfig(AudioInputConfigBase):
  out_topic: int

class AudioInputTask(SyncTask):
  def __init__(self, client: Client, config: AudioInputConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.bytes_per_second = get_audio_bytes_per_time_sample(config.sample_format, config.channels) * config.rate

  @asynccontextmanager
  async def init(self):
    async with self.out_topic, self.out_topic.RegisterContext():
      self.client.start()
      yield

  def run_sync(self):
    audio = pyaudio.PyAudio()
    stream = audio.open(self.config.rate, self.config.channels, SAMPLE_FORMAT_2_PA_TYPE[self.config.sample_format], input=True,
                        frames_per_buffer=self.config.buffer_size, input_device_index=None if self.config.input_id == -1 else self.config.input_id)
    min_next_timestamp = 0

    while not self.stop_event.is_set():
      data = stream.read(self.config.buffer_size)
      timestamp = max(get_timestamp_ms(), min_next_timestamp)
      frame_duration = len(data) * 1000 // self.bytes_per_second
      min_next_timestamp = timestamp + frame_duration
      self.send_data(self.out_topic, RawData(TimestampChuckMessage(timestamp=timestamp, data=data).model_dump()))

class AudioInputTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="audio input",
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "audio", "codec": "raw" }],
    default_config=AudioInputConfigBase().model_dump(),
    config_to_output_map=[ { v: v for v in [ "rate", "channels", "sample_format" ] } ],
    editor_fields=[
      MediaEditorFields.sample_format(allowed_values=set(SAMPLE_FORMAT_2_PA_TYPE.keys())),
      MediaEditorFields.channel_count(),
      MediaEditorFields.sample_rate(),
      EditorFields.integer(key="input_id", label="id/index of the input device (-1 to automatically select)", min_value=-1),
      MediaEditorFields.audio_buffer_size()
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return AudioInputTask(await self.create_client(topic_space_id), AudioInputConfig.model_validate(config))
