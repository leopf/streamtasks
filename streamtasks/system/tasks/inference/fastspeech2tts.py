import asyncio
from typing import Any
import numpy as np
from pydantic import BaseModel, ValidationError
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import TextMessage, TimestampChuckMessage
from streamtasks.net.message.types import TopicControlData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from speechbrain.inference.TTS import FastSpeech2
from speechbrain.inference.vocoders import HIFIGAN

from streamtasks.system.tasks.inference.utils import get_model_data_dir

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

class FastSpeech2Runner:
  def __init__(self, hifi_gan: HIFIGAN, fastspeech2: FastSpeech2, config: FastSpeech2TTSConfigBase) -> None:
    self.hifi_gan = hifi_gan
    self.fastspeech2 = fastspeech2
    self.config = config

  def run(self, text: str) -> np.ndarray:
    mel_output, _, _, _ = self.fastspeech2.encode_text([text], pace=self.config.pace, pitch_rate=self.config.pitch, energy_rate=1.0)
    return self.hifi_gan.decode_batch(mel_output).cpu().numpy()

class FastSpeech2TTSTask(Task):
  def __init__(self, client: Client, config: FastSpeech2TTSConfig):
    super().__init__(client)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config

  async def run(self):
    loop = asyncio.get_running_loop()
    runner = await loop.run_in_executor(None, self.load_models)

    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      while True:
        try:
          data = await self.in_topic.recv_data_control()
          if isinstance(data, TopicControlData): await self.out_topic.set_paused(data.paused)
          else:
            message = TextMessage.model_validate(data.data)
            samples = await loop.run_in_executor(None, runner.run, message.value)
            await self.out_topic.send(MessagePackData(TimestampChuckMessage(timestamp=message.timestamp, data=samples.tobytes("C")).model_dump()))
        except (ValidationError, ValueError): pass

  def load_models(self):
    hifi_gan =  HIFIGAN.from_hparams(source="speechbrain/tts-hifigan-ljspeech", savedir=get_model_data_dir("pretrained_models/tts-hifigan-ljspeech"), run_opts={ "device":self.config.device })
    if hifi_gan is None: raise FileNotFoundError("Did not find HIFIGAN!")
    fastspeech2 = FastSpeech2.from_hparams(self.config.source, savedir=get_model_data_dir(self.config.source), run_opts={ "device":self.config.device })
    if fastspeech2 is None: raise FileNotFoundError("Did not find FastSpeech2!")
    return FastSpeech2Runner(hifi_gan, fastspeech2, self.config)

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
