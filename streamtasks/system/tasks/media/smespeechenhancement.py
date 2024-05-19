import asyncio
from fractions import Fraction
import re
from typing import Any
import numpy as np
from pydantic import BaseModel, ValidationError
from streamtasks.env import get_data_sub_dir
from streamtasks.media.audio import audio_buffer_to_ndarray
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import TimestampChuckMessage
from streamtasks.net.message.types import TopicControlData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from speechbrain.inference.enhancement import SpectralMaskEnhancement
import torch

_SAMPLE_RATE = 16000

class SMESpeechEnhancementConfigBase(BaseModel):
  source: str = "speechbrain/metricgan-plus-voicebank"
  device: str = "cpu"
  buffer_duration: int = 1000

  @property
  def buffer_size(self): return self.buffer_duration * _SAMPLE_RATE // 1000

  @property
  def buffer_keep(self): return self.buffer_size // 4

class SMESpeechEnhancementConfig(SMESpeechEnhancementConfigBase):
  out_topic: int
  in_topic: int

class SMESpeechEnhancementTask(Task):
  def __init__(self, client: Client, config: SMESpeechEnhancementConfig):
    super().__init__(client)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.sample_buffer = np.array([], dtype=np.float32)
    self.config = config

  async def run(self):
    loop = asyncio.get_running_loop()
    model = await loop.run_in_executor(None, self.load_model)
    if model is None: raise FileNotFoundError("The model could not be loaded from the specified source!")
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      while True:
        try:
          data = await self.in_topic.recv_data_control()
          if isinstance(data, TopicControlData): await self.out_topic.set_paused(data.paused)
          else:
            message = TimestampChuckMessage.model_validate(data.data)
            new_samples = audio_buffer_to_ndarray(message.data, "flt")[0]
            self.sample_buffer = np.concatenate((self.sample_buffer, new_samples))

            while self.sample_buffer.size >= self.config.buffer_size:
              samples = torch.from_numpy(self.sample_buffer.reshape((1, -1)).copy())
              result: torch.Tensor = model.enhance_batch(samples, lengths=torch.tensor([1.])).flatten()
              result = result * (np.abs(self.sample_buffer).mean() / result.abs().mean().item())

              out_samples: np.ndarray = result[self.config.buffer_keep:-self.config.buffer_keep].numpy()

              timestamp = message.timestamp + int((-self.sample_buffer.size + self.config.buffer_keep) * Fraction(1000, _SAMPLE_RATE))
              await self.out_topic.send(MessagePackData(TimestampChuckMessage(timestamp=timestamp, data=out_samples.tobytes("C")).model_dump()))
              self.sample_buffer = self.sample_buffer[-2*self.config.buffer_keep:]
        except (ValidationError, ValueError): pass

  def load_model(self):
    save_dir = get_data_sub_dir("./models/" + re.sub("[^a-z0-9\\-]", "", self.config.source))
    return SpectralMaskEnhancement.from_hparams(self.config.source, savedir=save_dir, run_opts={ "device":self.config.device })

class SMESpeechEnhancementTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="SME Speech Enhancement",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "content": "audio", "codec": "raw", "rate": _SAMPLE_RATE, "channels": 1, "sample_format": "flt" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "audio", "codec": "raw", "rate": _SAMPLE_RATE, "channels": 1, "sample_format": "flt" }],
    default_config=SMESpeechEnhancementConfigBase().model_dump(),
    editor_fields=[
      EditorFields.text(key="source", label="source (path or model name)"),
      EditorFields.text(key="device"),
      EditorFields.number(key="buffer_duration", is_int=True, unit="ms")
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return SMESpeechEnhancementTask(await self.create_client(topic_space_id), SMESpeechEnhancementConfig.model_validate(config))
