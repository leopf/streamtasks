import asyncio
from typing import Any
import numpy as np
from pydantic import BaseModel, ValidationError
from streamtasks.media.audio import audio_buffer_to_ndarray
from streamtasks.media.util import AudioSmoother, PaddedAudioChunker
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import TimestampChuckMessage
from streamtasks.net.message.types import TopicControlData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from speechbrain.inference.enhancement import WaveformEnhancement
import torch

from streamtasks.system.tasks.inference.utils import get_model_data_dir

_SAMPLE_RATE = 16000

class WaveformSpeechEnhancementConfigBase(BaseModel):
  source: str = "speechbrain/mtl-mimic-voicebank"
  device: str = "cpu"
  buffer_duration: int = 1000

  @property
  def buffer_size(self): return self.buffer_duration * _SAMPLE_RATE // 1000

  @property
  def buffer_padding(self): return self.buffer_size // 4

class WaveformSpeechEnhancementConfig(WaveformSpeechEnhancementConfigBase):
  out_topic: int
  in_topic: int

class WaveformSpeechEnhancementTask(Task):
  def __init__(self, client: Client, config: WaveformSpeechEnhancementConfig):
    super().__init__(client)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config

  async def run(self):
    loop = asyncio.get_running_loop()
    model = await loop.run_in_executor(None, self.load_model)
    if model is None: raise FileNotFoundError("The model could not be loaded from the specified source!")

    chunker = PaddedAudioChunker(self.config.buffer_size, _SAMPLE_RATE, self.config.buffer_padding)
    decracker = AudioSmoother(self.config.buffer_padding * 2)

    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      while True:
        try:
          data = await self.in_topic.recv_data_control()
          if isinstance(data, TopicControlData): await self.out_topic.set_paused(data.paused)
          else:
            message = TimestampChuckMessage.model_validate(data.data)
            for chunk, timestamp in chunker.next(audio_buffer_to_ndarray(message.data, "flt")[0], message.timestamp):
              samples = torch.from_numpy(chunk.reshape((1, -1)).copy())
              result: torch.Tensor = (await loop.run_in_executor(None, model.enhance_batch, samples, torch.tensor([1.]))).flatten()
              result = result * (np.abs(chunk).mean() / result.abs().mean().item()) # scale to prevent volume changes
              out_samples: np.ndarray = chunker.strip_padding(decracker.smooth(result.cpu().numpy()))
              await self.out_topic.send(MessagePackData(TimestampChuckMessage(timestamp=timestamp, data=out_samples.tobytes("C")).model_dump()))
        except (ValidationError, ValueError): pass

  def load_model(self):
    return WaveformEnhancement.from_hparams(self.config.source, savedir=get_model_data_dir(self.config.source), run_opts={ "device":self.config.device })

class WaveformSpeechEnhancementTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="Waveform Speech Enhancement",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "content": "audio", "codec": "raw", "rate": _SAMPLE_RATE, "channels": 1, "sample_format": "flt" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "audio", "codec": "raw", "rate": _SAMPLE_RATE, "channels": 1, "sample_format": "flt" }],
    default_config=WaveformSpeechEnhancementConfigBase().model_dump(),
    editor_fields=[
      EditorFields.text(key="source", label="source (path or model name)"),
      EditorFields.text(key="device"),
      EditorFields.integer(key="buffer_duration", unit="ms")
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return WaveformSpeechEnhancementTask(await self.create_client(topic_space_id), WaveformSpeechEnhancementConfig.model_validate(config))
