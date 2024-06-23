from contextlib import asynccontextmanager
import queue
from typing import Any
import numpy as np
from pydantic import BaseModel, ValidationError
from streamtasks.net.serialization import RawData
from streamtasks.message.types import TextMessage, TimestampChuckMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client
from speechbrain.inference.TTS import FastSpeech2
from speechbrain.inference.vocoders import HIFIGAN
from streamtasks.system.tasks.inference.utils import get_model_data_dir
from streamtasks.utils import context_task

_SAMPLE_RATE = 22050

class FastSpeech2TTSConfigBase(BaseModel):
  source: str = "speechbrain/tts-fastspeech2-ljspeech"
  device: str = "cpu"
  pace: float = 1
  energy: float = 1
  pitch: float = 1

class FastSpeech2TTSConfig(FastSpeech2TTSConfigBase):
  out_topic: int
  in_topic: int

class FastSpeech2TTSTask(SyncTask):
  def __init__(self, client: Client, config: FastSpeech2TTSConfig):
    super().__init__(client)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.message_queue: queue.Queue[TextMessage] = queue.Queue()

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
        else: self.message_queue.put(TextMessage.model_validate(data.data))
      except (ValidationError, ValueError): pass

  def run_sync(self):
    hifi_gan =  HIFIGAN.from_hparams(source="speechbrain/tts-hifigan-ljspeech", savedir=get_model_data_dir("pretrained_models/tts-hifigan-ljspeech"), run_opts={ "device":self.config.device })
    if hifi_gan is None: raise FileNotFoundError("Did not find HIFIGAN!")
    fastspeech2 = FastSpeech2.from_hparams(self.config.source, savedir=get_model_data_dir(self.config.source), run_opts={ "device":self.config.device })
    if fastspeech2 is None: raise FileNotFoundError("Did not find FastSpeech2!")

    while not self.stop_event.is_set():
      try:
        message = self.message_queue.get(timeout=0.5)
        mel_output, _, _, _ = fastspeech2.encode_text([message.value], pace=self.config.pace, pitch_rate=self.config.pitch, energy_rate=1.0)
        samples: np.ndarray = hifi_gan.decode_batch(mel_output).cpu().numpy()
        self.send_data(self.out_topic, RawData(TimestampChuckMessage(timestamp=message.timestamp, data=samples.tobytes("C")).model_dump()))
      except queue.Empty: pass

class FastSpeech2TTSTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="TTS Fast Speech 2",
    inputs=[{ "label": "text", "type": "ts", "key": "in_topic", "content": "text" }],
    outputs=[{ "label": "speech", "type": "ts", "key": "out_topic", "content": "audio", "codec": "raw", "rate": _SAMPLE_RATE, "channels": 1, "sample_format": "flt" }],
    default_config=FastSpeech2TTSConfigBase().model_dump(),
    editor_fields=[
      EditorFields.text(key="source", label="source (path or model name)"),
      EditorFields.text(key="device"),
      EditorFields.number(key="pitch", min_value=0),
      EditorFields.number(key="pace", min_value=0),
      EditorFields.number(key="energy", min_value=0),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return FastSpeech2TTSTask(await self.create_client(topic_space_id), FastSpeech2TTSConfig.model_validate(config))
