import ctypes
import ctypes.util
from dataclasses import dataclass
from typing import Iterator, Literal
import av
import av.codec
import numpy as np
from streamtasks.utils import strip_nones_from_dict

lib = ctypes.CDLL(ctypes.util.find_library("avutil"))

av_get_pix_fmt_name = lib.av_get_pix_fmt_name
av_get_pix_fmt_name.argtypes = [ctypes.c_int]
av_get_pix_fmt_name.restype = ctypes.c_char_p

av_get_sample_fmt_name = lib.av_get_sample_fmt_name
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
  name: str
  type: Literal["audio", "video"]

def list_available_codecs(mode: Literal["r", "w"]) -> Iterator[CodecInfo]:
  for name in av.codecs_available:
    try:
      c = av.codec.Codec(name, mode)
      yield CodecInfo(name=name, type=c.type)
    except BaseException: pass

def list_sorted_available_codecs(mode: Literal["r", "w"]) -> Iterator[CodecInfo]: return sorted(list_available_codecs(mode), key=lambda c: c.name)

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
