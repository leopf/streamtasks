import ctypes
import ctypes.util
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterator, Literal
import av
import av.codec
import numpy as np
from streamtasks.debugging import ddebug_value
from streamtasks.env import DEBUG_MIXER
from streamtasks.utils import strip_nones_from_dict

# TODO: memory management

libavutil = ctypes.CDLL(ctypes.util.find_library("avutil"))
libavcodec = ctypes.CDLL(ctypes.util.find_library("avcodec"))

avcodec_get_name = libavcodec.avcodec_get_name
avcodec_get_name.argtypes = [ctypes.c_int]
avcodec_get_name.restype = ctypes.c_char_p

av_get_pix_fmt_name = libavutil.av_get_pix_fmt_name
av_get_pix_fmt_name.argtypes = [ctypes.c_int]
av_get_pix_fmt_name.restype = ctypes.c_char_p

av_get_sample_fmt_name = libavutil.av_get_sample_fmt_name
av_get_sample_fmt_name.argtypes = [ctypes.c_int]
av_get_sample_fmt_name.restype = ctypes.c_char_p

def list_pixel_formats() -> list[str]:
  names = []
  format_idx = 0
  while (name := av_get_pix_fmt_name(format_idx)):
    names.append(name.decode("utf-8"))
    format_idx += 1
  names.sort()
  return names

def list_sample_formats() -> list[str]:
  names = []
  format_idx = 0
  while (name := av_get_sample_fmt_name(format_idx)):
    names.append(name.decode("utf-8"))
    format_idx += 1
  names.sort()
  return names

@dataclass
class CodecInfo:
  id: int
  coder_name: str # the name of encoder / decoder
  type: Literal["audio", "video"]

  @property
  def codec_name(self): return avcodec_get_name(self.id).decode("utf-8")

def list_available_codecs(mode: Literal["r", "w"]) -> Iterator[CodecInfo]:
  for name in av.codecs_available:
    try:
      c = av.codec.Codec(name, mode)
      yield CodecInfo(id=c.id, coder_name=name, type=c.type)
    except BaseException: pass

def list_sorted_available_codecs(mode: Literal["r", "w"]) -> Iterator[CodecInfo]: return sorted(list_available_codecs(mode), key=lambda c: c.coder_name)

def list_codec_formats(name: str, mode: Literal["r", "w"]):
  c = av.codec.Codec(name, mode)
  if c.type == "audio": return [ f.name for f in c.audio_formats ]
  if c.type == "video": return [ f.name for f in c.video_formats ]

def options_from_codec_context(ctx: av.codec.context.CodecContext) -> dict[str, str]:
    return strip_nones_from_dict({ "bit_rate": None if ctx.bit_rate is None else str(ctx.bit_rate), "bit_rate_tolerance": None if ctx.bit_rate_tolerance is None else str(ctx.bit_rate_tolerance)  })

class AudioChunker:
  def __init__(self, chunk_size: int, sample_rate: int) -> None:
    self.chunk_size = chunk_size
    self.sample_rate = sample_rate
    self.buffer_duration = 1000 * chunk_size // sample_rate
    self.buffer: np.ndarray | None = None

  @property
  def buffer_size(self): return 0 if self.buffer is None else self.buffer.size

  def next(self, buf: np.ndarray, timestamp: int):
    current_timestamp = timestamp - self.buffer_size * 1000 // self.sample_rate
    self.buffer = buf.flatten() if self.buffer is None else np.concatenate((self.buffer, buf.flatten()))

    while self.buffer.size > self.chunk_size:
      yield (self.buffer[:self.chunk_size], current_timestamp)
      self.buffer = self.buffer[self.chunk_size:]
      current_timestamp += self.buffer_duration

class PaddedAudioChunker:
  def __init__(self, chunk_size: int, sample_rate: int, padding: int) -> None:
    self.chunk_size = chunk_size
    self.sample_rate = sample_rate
    self.padding = padding
    self.process_buffer_size = self.chunk_size + 2 * self.padding
    self.buffer_duration = 1000 * chunk_size // sample_rate
    self.buffer: np.ndarray | None = None

  @property
  def buffer_size(self): return 0 if self.buffer is None else self.buffer.size

  def next(self, buf: np.ndarray, timestamp: int):
    current_timestamp = timestamp - (self.buffer_size - self.padding) * 1000 // self.sample_rate
    self.buffer = buf.flatten() if self.buffer is None else np.concatenate((self.buffer, buf.flatten()))

    while self.buffer.size > self.process_buffer_size:
      yield (self.buffer[:self.process_buffer_size], current_timestamp)
      self.buffer = self.buffer[self.chunk_size:]
      current_timestamp += self.buffer_duration

  def strip_padding(self, buf: np.ndarray): return buf[self.padding:-self.padding]

class AudioSmoother:
  def __init__(self, overlap: int) -> None:
    self.buffer: np.ndarray | None = None
    self.scale_old = np.linspace(1, 0, num=overlap)
    self.scale_new = np.linspace(0, 1, num=overlap)
    self.overlap = overlap

  def smooth(self, buf: np.ndarray):
    assert buf.size > self.overlap
    old_overlap = self.buffer
    self.buffer = buf[-self.overlap:].copy()
    if old_overlap is not None:
      buf[:self.overlap] = buf[:self.overlap] * self.scale_new + old_overlap * self.scale_old
    return buf

class AudioSequencer:
  def __init__(self, sample_rate: int, max_stretch_ratio: float, keep_buffer_size: int) -> None:
    self._sample_rate = sample_rate
    self._desync_time = Fraction(0)
    self._buffer_start_time: Fraction | None = None
    self._sample_buffer: np.ndarray | None = None
    self._keep_buffer_size = keep_buffer_size
    assert max_stretch_ratio >= 1
    self._max_stretch_ratio = max_stretch_ratio

  @property
  def start_time(self): return self._buffer_start_time

  @property
  def end_time(self): return self._buffer_start_time + Fraction(self._sample_buffer.shape[0], self._sample_rate)

  @property
  def started(self): return self._sample_buffer is not None and self._buffer_start_time is not None

  def reset(self, force: bool = False):
    if self._sample_buffer is None or self._buffer_start_time is None or self._sample_buffer.size == 0 or force:
      self._sample_buffer = None
      self._buffer_start_time = None
      self._desync_time = Fraction(0)

  def get_max_samples(self, time: Fraction) -> int: return max(0, self._sample_buffer.shape[0] - self._get_start_sample_offset(time) - self._keep_buffer_size)
  def pop_start(self, time: Fraction, sample_count: int) -> np.ndarray:
    if self._sample_buffer is None or self._buffer_start_time is None: return self._make_zeros(sample_count)
    start_offset = self._get_start_sample_offset(time)
    buf_end = max(0, min(sample_count + start_offset, self._sample_buffer.shape[0]))
    buf_start = min(max(0, start_offset), self._sample_buffer.shape[0])
    pad_count = min(max(0, -start_offset), sample_count)
    result = np.concatenate((self._make_zeros(pad_count), self._sample_buffer[buf_start:buf_end]), axis=0)
    self._sample_buffer = self._sample_buffer[buf_end:]
    self._buffer_start_time += Fraction(buf_end, self._sample_rate)
    assert result.shape[0] <= sample_count, "more samples than allowed were popped"
    if result.shape[0] < sample_count: result = np.concatenate((result, self._make_zeros(sample_count - result.shape[0])),  axis=0)
    return result

  def insert(self, time: Fraction, samples: np.ndarray):
    assert len(samples.shape) == 2, "expected samples to be in shape (time, channels)"
    assert self._sample_buffer is None or self._sample_buffer.dtype == samples.dtype
    assert self._sample_buffer is None or self._sample_buffer.shape[1] == samples.shape[1]

    if self._buffer_start_time is None or self._sample_buffer is None:
      self._sample_buffer = samples
      self._buffer_start_time = time
    else:
      self._desync_time += time - self.end_time
      next_sample_count = self._sample_buffer.shape[0] + samples.shape[0]
      desync_sample_count: int = round(abs(self._desync_time) * self._sample_rate)
      if DEBUG_MIXER(): ddebug_value("track desync time", id(self), float(self._desync_time))
      if desync_sample_count > 0:
        if self._desync_time < 0:
          new_buf_length = self._sample_buffer.shape[0] + samples.shape[0] - desync_sample_count
          if new_buf_length > 0 and next_sample_count / new_buf_length < self._max_stretch_ratio:
            self._sample_buffer = np.concatenate((self._sample_buffer, samples), axis=0)
            self._strech_sample_buffer(new_buf_length)
          else:
            self._sample_buffer = np.concatenate((self._sample_buffer, samples[desync_sample_count:]), axis=0)
          self._desync_time += Fraction(min(desync_sample_count, samples.shape[0]), self._sample_rate)
        else:
          new_buf_length = self._sample_buffer.shape[0] + desync_sample_count + samples.shape[0]
          if next_sample_count != 0 and new_buf_length / next_sample_count < self._max_stretch_ratio:
            self._sample_buffer = np.concatenate((self._sample_buffer, samples), axis=0)
            self._strech_sample_buffer(new_buf_length)
          else:
            self._sample_buffer = np.concatenate((self._sample_buffer, self._make_zeros(desync_sample_count), samples), axis=0)
          self._desync_time -= Fraction(desync_sample_count, self._sample_rate)
      else: self._sample_buffer = np.concatenate((self._sample_buffer, samples), axis=0)


  def _strech_sample_buffer(self, new_length: int):
    assert len(self._sample_buffer.shape) == 2
    original_indices = np.linspace(0, self._sample_buffer.shape[0] - 1, num=self._sample_buffer.shape[0])
    new_indices = np.linspace(0, self._sample_buffer.shape[0] - 1, num=new_length)
    out_array = np.empty_like(self._sample_buffer, shape=(new_length, self._sample_buffer.shape[1]))
    for i in range(self._sample_buffer.shape[1]):
      out_array[:, i] = np.interp(new_indices, original_indices, self._sample_buffer[:, i])
    self._sample_buffer = out_array
  def _make_zeros(self, sample_count: int) -> np.ndarray: return np.zeros((sample_count, self._sample_buffer.shape[1]), dtype=self._sample_buffer.dtype)
  def _get_start_sample_offset(self, time: Fraction) -> int: return int((time - self._buffer_start_time) * self._sample_rate)
