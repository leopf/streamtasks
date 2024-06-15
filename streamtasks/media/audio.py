from dataclasses import dataclass
from functools import cached_property
from typing import ByteString
import av.audio
import av.audio.codeccontext
import av.codec
from streamtasks.debugging import ddebug_value
from streamtasks.env import DEBUG_MEDIA
from streamtasks.media.codec import CodecInfo, Frame, Reformatter
import numpy as np
import asyncio
import av
from streamtasks.media.util import options_from_codec_context

_SAMPLE_FORMAT_NP_2_AV_INFO: dict[str, tuple[bool, type[np.dtype]]] = {
  "dbl": (False, np.float64),
  "dblp": (True, np.float64),
  "flt": (False, np.float32),
  "fltp": (True, np.float32),
  "s16": (False, np.int16),
  "s16p": (True, np.int16),
  "s32": (False, np.int32),
  "s32p": (True, np.int32),
  "s64": (False, np.int64),
  "s64p": (True, np.int64),
  "u8": (False, np.int8),
  "u8p": (True, np.int8),
}

def get_audio_bytes_per_time_sample(sample_format: str, channels: int): # time sample != sample, time sample has all channels
  if sample_format not in _SAMPLE_FORMAT_NP_2_AV_INFO: raise ValueError("Invalid sample format!")
  return _SAMPLE_FORMAT_NP_2_AV_INFO[sample_format][1]().itemsize * channels

def audio_buffer_to_ndarray(buf: ByteString, sample_format: str): # TODO: endianness
  if sample_format not in _SAMPLE_FORMAT_NP_2_AV_INFO: raise ValueError("Invalid sample format!")
  is_planar, dtype = _SAMPLE_FORMAT_NP_2_AV_INFO[sample_format]
  return np.frombuffer(buf, dtype=dtype), is_planar

def audio_buffer_to_samples(buf: ByteString, sample_format: str, channels: int):
  arr, is_planar = audio_buffer_to_ndarray(buf, sample_format)
  return arr.reshape((channels, -1) if is_planar else (-1, channels))

def sample_format_to_dtype(sample_format: str):
  if sample_format not in _SAMPLE_FORMAT_NP_2_AV_INFO: raise ValueError("Invalid sample format!")
  return _SAMPLE_FORMAT_NP_2_AV_INFO[sample_format][1]

class AudioFrame(Frame[av.AudioFrame]):
  def to_ndarray(self):
    return self.frame.to_ndarray()

  def to_bytes(self) -> bytes: return self.to_ndarray().tobytes("C")

  @staticmethod
  def from_ndarray(ndarray: np.ndarray, sample_format: str, channels: int, sample_rate: int):
    av_frame = av.AudioFrame.from_ndarray(ndarray, sample_format, channels)
    av_frame.sample_rate = sample_rate
    return AudioFrame(av_frame)

  @staticmethod
  def from_buffer(buf: ByteString, sample_format: str, channels: int, sample_rate: int):
    arr, is_planar = audio_buffer_to_ndarray(buf, sample_format)
    if is_planar: arr = arr.reshape((channels, -1))
    else: arr = arr.reshape((1, -1))
    return AudioFrame.from_ndarray(arr, sample_format, channels, sample_rate)

@dataclass
class AudioResamplerInfo:
  sample_format: str
  channels: int
  rate: int

  @property
  def layout(self): return av.AudioLayout(self.channels)

  @property
  def format(self): return av.AudioFormat(self.sample_format)

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

  @property
  def resampler_info(self): return AudioResamplerInfo(sample_format=self.sample_format, channels=self.channels, rate=self.rate)

  @cached_property
  def codec_id(self):
    try: return av.Codec(self.codec, "r").id
    except: pass
    try: return av.Codec(self.codec, "w").id
    except: pass
    raise ValueError("Codec not found!")

  def compatible_with(self, other: 'CodecInfo') -> bool:
    if not isinstance(other, AudioCodecInfo): return False
    return self.codec_id == other.codec_id and self.channels == other.channels and self.sample_rate == other.sample_rate and self.sample_format == other.sample_format

  def get_reformatter(self, from_codec: 'AudioCodecInfo') -> Reformatter: return AudioResampler(self.resampler_info, from_codec.resampler_info)
  def get_resampler(self): return AudioResampler(self.resampler_info)

  def _get_av_codec_context(self, mode: str):
    if mode not in ('r', 'w'): raise ValueError(f'Invalid mode: {mode}. Must be "r" or "w".')
    ctx: av.audio.codeccontext.AudioCodecContext = av.audio.codeccontext.AudioCodecContext.create(self.codec, mode)
    ctx.format = self.to_av_format()
    ctx.channels = self.channels
    ctx.sample_rate = self.sample_rate
    ctx.options.update(self.options)

    if "threads" in self.options: ctx.thread_count = int(self.options["threads"])
    if "bit_rate" in self.options: ctx.bit_rate = int(self.options["bit_rate"])
    if "bit_rate_tolerance" in self.options: ctx.bit_rate_tolerance = int(self.options["bit_rate_tolerance"])

    if mode == 'w':
      ctx.time_base = self.time_base

    return ctx

  @staticmethod
  def from_codec_context(ctx: av.audio.codeccontext.AudioCodecContext):
    return AudioCodecInfo(ctx.name, ctx.channels, ctx.sample_rate, ctx.format.name, options_from_codec_context(ctx))

class AudioResampler(Reformatter):
  def __init__(self, to_codec: AudioResamplerInfo, from_codec: AudioResamplerInfo | None = None):
    super().__init__()
    self.resampler = av.AudioResampler(to_codec.format, to_codec.layout, to_codec.rate)
    self.from_codec = from_codec
    self.min_pts = -2**31

  async def reformat(self, frame: AudioFrame) -> list[AudioFrame]:
    loop = asyncio.get_running_loop()
    if self.from_codec is not None:
      frame.frame.rate = self.from_codec.rate
    av_frames = await loop.run_in_executor(None, self.resampler.resample, frame.frame)
    frames: list[AudioFrame] = []

    for av_frame in av_frames:
      ts = av_frame.dts if av_frame.pts is None else av_frame.pts
      av_frame.pts = ts
      av_frame.dts = ts

      frames.append(AudioFrame(av_frame))
    if DEBUG_MEDIA():
      for f in frames:
        ddebug_value("audio frame at duration", float(f.dtime or 0))
    return frames
