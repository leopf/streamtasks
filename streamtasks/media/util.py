import ctypes
import ctypes.util
from dataclasses import dataclass
from typing import Iterator, Literal
import av
import av.codec
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
  