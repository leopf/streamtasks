from typing import Optional
from streamtasks.media.config import *
from streamtasks.message import MediaPacket
from streamtasks.media.codec import CodecInfo, Frame
import numpy as np
import time
import asyncio
import av

class AudioFrame(Frame[av.audio.frame.AudioFrame]):
  def to_ndarray(self):
    return self.frame.to_ndarray()

  @staticmethod
  def from_ndarray(ndarray: np.ndarray, sample_format: str, channels: int, sample_rate: int):
    av_frame = av.audio.frame.AudioFrame.from_ndarray(ndarray, sample_format, channels)
    av_frame.sample_rate = sample_rate
    return AudioFrame(av_frame)

class AudioCodecInfo(CodecInfo[AudioFrame]):
  channels: int # NOTE: may be insufficient
  sample_rate: int
  sample_format: str # NOTE: may be insufficient
  bitrate: Optional[int]
  crf: Optional[int]

  def __init__(self, codec: str, channels: int, sample_rate: int, sample_format: str, bitrate: Optional[int] = None, crf: Optional[int] = None):
    super().__init__(codec)
    self.bitrate = bitrate
    self.channels = channels
    self.sample_rate = sample_rate
    self.sample_format = sample_format
    self.crf = crf

  def to_av_format(self):
    return av.audio.format.AudioFormat(self.sample_format)

  def to_av_layout(self):
    return av.audio.layout.AudioLayout(self.channels)

  @property
  def type(self): return 'audio'

  @property
  def rate(self) -> Optional[int]: self.sample_rate

  def compatible_with(self, other: 'CodecInfo') -> bool:
    if not isinstance(other, AudioCodecInfo): return False
    return self.codec == other.codec and self.channels == other.channels and self.sample_rate == other.sample_rate and self.sample_format == other.sample_format

  def get_resampler(self):
    return AudioResampler(self.to_av_format(), self.to_av_layout(), self.sample_rate)

  def _get_av_codec_context(self, mode: str):
    assert mode in ('r', 'w'), f'Invalid mode: {mode}. Must be "r" or "w".'
    ctx = av.codec.CodecContext.create(self.codec, mode)
    ctx.format = self.to_av_format()
    ctx.channels = self.channels
    ctx.sample_rate = self.sample_rate

    if mode == 'w':
      ctx.time_base = DEFAULT_TIME_BASE
      if self.crf is not None:
        ctx.options['crf'] = str(self.crf)
      if self.bitrate is not None:
        ctx.bit_rate = self.bitrate

    return ctx

  @staticmethod
  def from_codec_context(ctx: av.codec.CodecContext):
    format = ctx.format
    return AudioCodecInfo(ctx.name, ctx.channels, ctx.sample_rate, format.name, ctx.bit_rate, ctx.options.get('crf', None))

class AudioResampler:
  def __init__(self, format: av.audio.format.AudioFormat, layout: av.audio.layout.AudioLayout, rate: int):
    self.resampler = av.audio.resampler.AudioResampler(format, layout, rate)

  async def resample(self, frame: AudioFrame) -> AudioFrame:
    loop = asyncio.get_running_loop()
    av_frames = await loop.run_in_executor(None, self.resampler.resample, frame.frame)
    return [ AudioFrame(av_frame) for av_frame in av_frames ]