import ctypes
import ctypes.util
from dataclasses import dataclass
from typing import Iterator, Literal
import av

class AVComponentDescriptor(ctypes.Structure):
  _fields_ = [
    ("plane", ctypes.c_uint),
    ("step", ctypes.c_uint),
    ("offset", ctypes.c_uint),
    ("shift", ctypes.c_uint),
    ("depth", ctypes.c_uint)
  ]

class AVPixFmtDescriptor(ctypes.Structure):
    _fields_ = [
      ("name", ctypes.c_char_p),
      ("nb_components", ctypes.c_uint8),
      ("log2_chroma_w", ctypes.c_uint8),
      ("log2_chroma_h", ctypes.c_uint8),
      ("flags", ctypes.c_uint8),
      ("comp", AVComponentDescriptor * 4)
    ]

lib = ctypes.CDLL(ctypes.util.find_library("avutil"))

av_pix_fmt_desc_get = lib.av_pix_fmt_desc_get
av_pix_fmt_desc_get.argtypes = [ctypes.c_int]
av_pix_fmt_desc_get.restype = ctypes.POINTER(AVPixFmtDescriptor)

av_pix_fmt_desc_next = lib.av_pix_fmt_desc_next
av_pix_fmt_desc_next.argtypes = [ctypes.POINTER(AVPixFmtDescriptor)]
av_pix_fmt_desc_next.restype = ctypes.POINTER(AVPixFmtDescriptor)

av_pix_fmt_desc_next = lib.av_pix_fmt_desc_next
av_pix_fmt_desc_next.argtypes = [ctypes.POINTER(AVPixFmtDescriptor)]
av_pix_fmt_desc_next.restype = ctypes.POINTER(AVPixFmtDescriptor)

av_get_pix_fmt_name = lib.av_get_pix_fmt_name
av_get_pix_fmt_name.argtypes = [ctypes.c_int]
av_get_pix_fmt_name.restype = ctypes.c_char_p

av_get_pix_fmt = lib.av_get_pix_fmt
av_get_pix_fmt.argtypes = [ctypes.c_char_p]
av_get_pix_fmt.restype = ctypes.c_int


def list_pixel_formats() -> list[str]:
  names = []
  format_idx = 0
  while (name := av_get_pix_fmt_name(format_idx)):
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
  