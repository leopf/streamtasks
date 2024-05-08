import asyncio
from typing import Any
from pydantic import BaseModel
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import TimestampChuckMessage
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from streamtasks.system.tasks.media.pa_utils import SAMPLE_FORMAT_2_PA_TYPE
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.utils import get_timestamp_ms
import pyaudio

class AudioInputConfigBase(BaseModel):
  sample_format: IOTypes.SampleFormat = "s16"
  channels: IOTypes.Channels = 1
  rate: IOTypes.Rate = 32000
  input_id: int = -1
  buffer_size: int = 1024
  
class AudioInputConfig(AudioInputConfigBase):
  out_topic: int

class AudioInputTask(Task):
  def __init__(self, client: Client, config: AudioInputConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    
  async def run(self):
    audio = pyaudio.PyAudio()
    stream = audio.open(self.config.rate, self.config.channels, SAMPLE_FORMAT_2_PA_TYPE[self.config.sample_format], input=True, 
                        frames_per_buffer=self.config.buffer_size, input_device_index=None if self.config.input_id == -1 else self.config.input_id)
    try:
      async with self.out_topic, self.out_topic.RegisterContext():
        self.client.start()
        loop = asyncio.get_running_loop()
        while True:
          data = await loop.run_in_executor(None, stream.read, self.config.buffer_size)
          await self.out_topic.send(MessagePackData(TimestampChuckMessage(timestamp=get_timestamp_ms(), data=data)))
    finally:
      stream.close()
    
class AudioInputTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="audio input",
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "audio", "codec": "raw" }],
    default_config=AudioInputConfigBase().model_dump(),
    config_to_input_map={ "in_topic": { **{ v: v for v in [ "rate", "channels", "sample_format" ] } } },
    config_to_output_map=[ { v: v for v in [ "rate", "channels", "sample_format" ] } ],
    editor_fields=[
      MediaEditorFields.sample_format(allowed_values=set(SAMPLE_FORMAT_2_PA_TYPE.keys())),
      MediaEditorFields.channel_count(),
      MediaEditorFields.sample_rate(),
      EditorFields.number(key="input_id", label="id/index of the input device (-1 to automatically select)", min_value=-1, is_int=True),
      MediaEditorFields.audio_buffer_size()
    ]
  )}
  async def create_task(self, config: Any, topic_space_id: int | None):
    return AudioInputTask(await self.create_client(topic_space_id), AudioInputConfig.model_validate(config))
  