from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.media.audio import audio_buffer_to_ndarray, sample_format_to_dtype
from streamtasks.media.util import AudioChunker
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import NumberMessage, TimestampChuckMessage
from streamtasks.net.message.types import TopicControlData
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
import numpy as np

from streamtasks.utils import TimeSynchronizer

class AudioVolumeMeterConfigBase(BaseModel):
  sample_format: IOTypes.SampleFormat = "s16"
  rate: IOTypes.SampleRate = 32000
  time_window: int = 1000

class AudioVolumeMeterConfig(AudioVolumeMeterConfigBase):
  out_topic: int
  in_topic: int

def max_dtype_value(dtype):
  if np.issubdtype(dtype, np.integer): return np.iinfo(dtype).max
  elif np.issubdtype(dtype, np.floating): return 1
  else: raise ValueError("Unsupported dtype")

class AudioVolumeMeterTask(Task):
  def __init__(self, client: Client, config: AudioVolumeMeterConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config
    sample_dtype = sample_format_to_dtype(self.config.sample_format)
    self.max_value = float(max_dtype_value(sample_dtype))
    self.sync = TimeSynchronizer()

  async def run(self):
    chunker = AudioChunker(self.config.rate * self.config.time_window // 1000, self.config.rate)
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      while True:
        try:
          data = await self.in_topic.recv_data_control()
          if isinstance(data, TopicControlData):
            if data.paused:
              await self.out_topic.send(MessagePackData(NumberMessage(timestamp=self.sync.time, value=0).model_dump()))
            await self.out_topic.set_paused(data.paused)
          else:
            message = TimestampChuckMessage.model_validate(data.data)
            for chunk, timestamp in chunker.next(audio_buffer_to_ndarray(message.data, self.config.sample_format)[0], message.timestamp):
              self.sync.update(timestamp)
              await self.out_topic.send(MessagePackData(NumberMessage(timestamp=timestamp, value=np.sqrt(np.mean(np.abs(chunk) / self.max_value))).model_dump()))
        except (ValidationError, ValueError): pass

class AudioVolumeMeterTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="audio volume meter",
    inputs=[{ "label": "audio", "type": "ts", "key": "in_topic", "content": "audio", "codec": "raw", "channels": 1 }],
    outputs=[{ "label": "volume", "type": "ts", "key": "out_topic", "content": "number" }],
    default_config=AudioVolumeMeterConfigBase().model_dump(),
    config_to_input_map={ "in_topic": { v: v for v in [ "rate", "sample_format" ] } },
    editor_fields=[
      MediaEditorFields.sample_format(),
      MediaEditorFields.sample_rate(),
      EditorFields.integer("time_window", min_value=1, unit="ms"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return AudioVolumeMeterTask(await self.create_client(topic_space_id), AudioVolumeMeterConfig.model_validate(config))
