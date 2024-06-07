from contextlib import asynccontextmanager
import queue
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.media.audio import audio_buffer_to_ndarray
from streamtasks.media.util import AudioChunker
from streamtasks.net.serialization import RawData
from streamtasks.message.types import TextMessage, TimestampChuckMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client
from speechbrain.inference.ASR import StreamingASR
from speechbrain.utils.dynamic_chunk_training import DynChunkTrainConfig
import torch

from streamtasks.system.tasks.inference.utils import get_model_data_dir
from streamtasks.utils import context_task

_SAMPLE_RATE = 16000

class ASRSpeechRecognitionConfigBase(BaseModel):
  source: str = "speechbrain/asr-streaming-conformer-librispeech"
  device: str = "cpu"
  chunk_size: int = 24
  left_context_size: int = 4

class ASRSpeechRecognitionConfig(ASRSpeechRecognitionConfigBase):
  out_topic: int
  in_topic: int

class ASRSpeechRecognitionTask(SyncTask):
  def __init__(self, client: Client, config: ASRSpeechRecognitionConfig):
    super().__init__(client)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.message_queue: queue.Queue[TimestampChuckMessage] = queue.Queue()

  @asynccontextmanager
  async def init(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext(), context_task(self._run_receiver()):
      self.client.start()
      yield

  async def _run_receiver(self):
    while True:
      try:
        data = await self.in_topic.recv_data_control()
        if isinstance(data, TopicControlData): await self.out_topic.set_paused(data.paused)
        else: self.message_queue.put(TimestampChuckMessage.model_validate(data.data))
      except (ValidationError, ValueError): pass

  def run_sync(self):
    try:
      model = StreamingASR.from_hparams(self.config.source, savedir=get_model_data_dir(self.config.source), run_opts={ "device":self.config.device })
      if model is None: raise FileNotFoundError("The model could not be loaded from the specified source!")

      streaming_context = model.make_streaming_context(DynChunkTrainConfig(chunk_size=self.config.chunk_size, left_context_size=self.config.left_context_size))
      chunker = AudioChunker(self.config.chunk_size * 320, _SAMPLE_RATE) # BUG: this is to prevent an assertion error in speechbrain about the chunk size

      while not self.stop_event.is_set():
        try:
          message = self.message_queue.get(timeout=0.5)
          for chunk, timestamp in chunker.next(audio_buffer_to_ndarray(message.data, "flt")[0], message.timestamp):
            samples = torch.from_numpy(chunk.reshape((1, -1)).copy())
            result: list[str] = model.transcribe_chunk(streaming_context, samples)
            if len(result[0]) > 0: self.send_data(self.out_topic, RawData(TextMessage(timestamp=timestamp, value=result[0].lower()).model_dump()))
        except queue.Empty: pass
    finally:
      if model: del model

class ASRSpeechRecognitionTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="ASR Speech Recognition",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "content": "audio", "codec": "raw", "rate": _SAMPLE_RATE, "channels": 1, "sample_format": "flt" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "text" }],
    default_config=ASRSpeechRecognitionConfigBase().model_dump(),
    editor_fields=[
      EditorFields.text(key="source", label="source (path or model name)"),
      EditorFields.text(key="device"),
      EditorFields.select(key="chunk_size", items=[ (v, str(v)) for v in [ 8, 12, 16, 24, 32 ] ]),
      EditorFields.integer(key="left_context_size", min_value=1, max_value=32, unit="chunks")
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return ASRSpeechRecognitionTask(await self.create_client(topic_space_id), ASRSpeechRecognitionConfig.model_validate(config))
