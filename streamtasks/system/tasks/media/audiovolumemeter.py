from contextlib import asynccontextmanager
import queue
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.media.audio import audio_buffer_to_ndarray, sample_format_to_dtype
from streamtasks.media.util import AudioChunker
from streamtasks.net.serialization import RawData
from streamtasks.message.types import NumberMessage, TimestampChuckMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client
import numpy as np
from streamtasks.utils import TimeSynchronizer, context_task

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

class AudioVolumeMeterTask(SyncTask):
  def __init__(self, client: Client, config: AudioVolumeMeterConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config
    sample_dtype = sample_format_to_dtype(self.config.sample_format)
    self.max_value = float(max_dtype_value(sample_dtype))
    self.message_queue: queue.Queue[TimestampChuckMessage] = queue.Queue()

  @asynccontextmanager
  async def init(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext(), context_task(self._run_receiver()):
      self.client.start()
      yield

  async def _run_receiver(self):
    sync = TimeSynchronizer()
    while True:
      try:
        data = await self.in_topic.recv_data_control()
        if isinstance(data, TopicControlData):
          if data.paused: await self.out_topic.send(RawData(NumberMessage(timestamp=sync.time, value=0).model_dump()))
          await self.out_topic.set_paused(data.paused)
        else:
          message = TimestampChuckMessage.model_validate(data.data)
          sync.update(message.timestamp)
          self.message_queue.put(message)
      except (ValidationError, ValueError): pass

  def run_sync(self):
    chunker = AudioChunker(self.config.rate * self.config.time_window // 1000, self.config.rate)
    while not self.stop_event.is_set():
      try:
        message = self.message_queue.get(timeout=0.5)
        for chunk, timestamp in chunker.next(audio_buffer_to_ndarray(message.data, self.config.sample_format)[0], message.timestamp):
          self.send_data(self.out_topic, RawData(NumberMessage(timestamp=timestamp, value=np.sqrt(np.mean(np.abs(chunk) / self.max_value))).model_dump()))
      except queue.Empty: pass

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
