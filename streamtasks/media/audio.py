from typing import Optional
from streamtasks.media.config import *
from streamtasks.media.types import MediaPacket
from streamtasks.media.codec import CodecInfo, Frame
import numpy as np
import time
import asyncio
import av

class AudioFrame(Frame[av.audio.frame.AudioFrame]):
  def to_ndarray(self):
    return self.frame.to_ndarray()

  @staticmethod
  def from_ndarray(ndarray: np.ndarray, sample_format: str, layout: str):
    return AudioFrame(av.audio.frame.AudioFrame.from_ndarray(ndarray, sample_format, layout))

class AudioCodecInfo(CodecInfo[AudioFrame]):
  channels: int # NOTE: may be insufficient
  sample_rate: int
  sample_format: str # NOTE: may be insufficient
  bitrate: Optional[int]
  crf: Optional[int]

  def __init__(self, codec: str, channels: int, sample_rate: int, sample_format: str, bitrate: Optional[int], crf: Optional[int] = None):
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

  def _get_av_codec_context(self, mode: str):
    assert mode in ('r', 'w'), f'Invalid mode: {mode}. Must be "r" or "w".'
    ctx = av.codec.CodecContext.create(self.codec, mode)
    ctx.format = self.to_av_format()
    ctx.layout = self.to_av_layout()
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
    layout = ctx.layout
    return AudioCodecInfo(ctx.name, ctx.channels, ctx.sample_rate, ctx.frame_size, format.name, ctx.bit_rate, ctx.options.get('crf', None))