from contextlib import asynccontextmanager
import queue
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.message.types import TimestampChuckMessage
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client
from streamtasks.system.tasks.media.pa_utils import SAMPLE_FORMAT_2_PA_TYPE
from streamtasks.system.tasks.media.utils import MediaEditorFields
import pyaudio

from streamtasks.utils import context_task

class AudioOutputConfigBase(BaseModel):
  sample_format: IOTypes.SampleFormat = "s16"
  channels: IOTypes.Channels = 1
  rate: IOTypes.SampleRate = 32000
  output_id: int = -1
  buffer_size: int = 1024

class AudioOutputConfig(AudioOutputConfigBase):
  in_topic: int

class AudioOutputTask(SyncTask):
  def __init__(self, client: Client, config: AudioOutputConfig):
    super().__init__(client)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config
    self.message_queue: queue.Queue[TimestampChuckMessage] = queue.Queue()

  @asynccontextmanager
  async def init(self):
    async with self.in_topic, self.in_topic.RegisterContext(), context_task(self._run_receiver()):
      self.client.start()
      yield

  async def _run_receiver(self):
    while True:
      try:
        data = await self.in_topic.recv_data()
        self.message_queue.put(TimestampChuckMessage.model_validate(data.data))
      except ValidationError: pass

  def run_sync(self):
    audio = pyaudio.PyAudio()
    stream = audio.open(self.config.rate, self.config.channels, SAMPLE_FORMAT_2_PA_TYPE[self.config.sample_format], output=True,
                        frames_per_buffer=self.config.buffer_size, output_device_index=None if self.config.output_id == -1 else self.config.output_id)
    try:
      while not self.stop_event.is_set():
        try:
          message = self.message_queue.get(timeout=0.5)
          stream.write(message.data)
        except queue.Empty: pass
    finally: stream.close()

class AudioOutputTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="audio output",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "content": "audio", "codec": "raw" }],
    default_config=AudioOutputConfigBase().model_dump(),
    config_to_input_map={ "in_topic": { v: v for v in [ "rate", "channels", "sample_format" ] } },
    editor_fields=[
      MediaEditorFields.sample_format(allowed_values=set(SAMPLE_FORMAT_2_PA_TYPE.keys())),
      MediaEditorFields.channel_count(),
      MediaEditorFields.sample_rate(),
      EditorFields.integer(key="output_id", label="id/index of the output device (-1 to automatically select)", min_value=-1),
      MediaEditorFields.audio_buffer_size()
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return AudioOutputTask(await self.create_client(topic_space_id), AudioOutputConfig.model_validate(config))
