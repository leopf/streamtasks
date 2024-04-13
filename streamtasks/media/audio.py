import av.audio
import av.audio.codeccontext
import av.codec
from streamtasks.media.codec import CodecInfo, Frame
import numpy as np
import asyncio
import av

class AudioFrame(Frame[av.AudioFrame]):
  def to_ndarray(self):
    return self.frame.to_ndarray()

  @staticmethod
  def from_ndarray(ndarray: np.ndarray, sample_format: str, channels: int, sample_rate: int):
    av_frame = av.AudioFrame.from_ndarray(ndarray, sample_format, channels)
    av_frame.sample_rate = sample_rate
    return AudioFrame(av_frame)


class AudioCodecInfo(CodecInfo[AudioFrame]):

  def __init__(self, codec: str, channels: int, sample_rate: int, sample_format: str, options: dict[str, str] = {}):
    super().__init__(codec)
    self.channels = channels
    self.sample_rate = sample_rate
    self.sample_format = sample_format
    self.options = options

  def to_av_format(self):
    return av.AudioFormat(self.sample_format)

  def to_av_layout(self):
    return av.AudioLayout(self.channels)

  @property
  def type(self): return 'audio'

  @property
  def rate(self) -> int: return self.sample_rate

  def compatible_with(self, other: 'CodecInfo') -> bool:
    if not isinstance(other, AudioCodecInfo): return False
    return self.codec == other.codec and self.channels == other.channels and self.sample_rate == other.sample_rate and self.sample_format == other.sample_format

  def get_resampler(self):
    return AudioResampler(self.to_av_format(), self.to_av_layout(), self.sample_rate)

  def _get_av_codec_context(self, mode: str):
    if mode not in ('r', 'w'): raise ValueError(f'Invalid mode: {mode}. Must be "r" or "w".')
    ctx: av.audio.codeccontext.AudioCodecContext = av.audio.codeccontext.AudioCodecContext.create(self.codec, mode)
    ctx.format = self.to_av_format()
    ctx.channels = self.channels
    ctx.sample_rate = self.sample_rate
    ctx.options.update(self.options)

    if "bit_rate" in self.options: ctx.bit_rate = int(self.options["bit_rate"])
    if "bit_rate_tolerance" in self.options: ctx.bit_rate_tolerance = int(self.options["bit_rate_tolerance"])
    
    if mode == 'w':
      ctx.time_base = self.time_base

    return ctx

  @staticmethod
  def from_codec_context(ctx: av.audio.codeccontext.AudioCodecContext):
    return AudioCodecInfo(ctx.name, ctx.channels, ctx.sample_rate, ctx.format.name)

class AudioResampler:
  def __init__(self, format: av.AudioFormat, layout: av.AudioLayout, rate: int):
    self.resampler = av.AudioResampler(format, layout, rate)

  async def resample(self, frame: AudioFrame) -> list[AudioFrame]:
    loop = asyncio.get_running_loop()
    av_frames = await loop.run_in_executor(None, self.resampler.resample, frame.frame)
    return [ AudioFrame(av_frame) for av_frame in av_frames ]