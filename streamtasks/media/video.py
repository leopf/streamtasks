import ctypes
from dataclasses import dataclass
from fractions import Fraction
from functools import cached_property
from typing import Any, ByteString, Literal
import av.video.reformatter
import av
import av.codec
import av.video
import av.video.codeccontext
import numpy as np
from streamtasks.media.codec import CodecInfo, Frame, Reformatter
from streamtasks.media.util import options_from_codec_context

# TODO: endianness
def video_buffer_to_ndarray(buf: ByteString, width: int, height: int):
  bitmap = np.frombuffer(buf, dtype=np.uint8).reshape((height, width, -1))
  if bitmap.shape[-1] == 1: bitmap = bitmap.squeeze()
  return bitmap

TRANSPARENT_PXL_FORMATS = { "rgba", "bgra", "abgr", "argb" }

class VideoFrame(Frame[av.VideoFrame]):
  def to_rgb(self):
    return VideoFrame(self.frame.to_rgb())

  def to_ndarray(self):
    return self.frame.to_ndarray()

  def convert(self, width: int | None = None, height: int | None = None, pixel_format: str | None = None):
    return VideoFrame(self.frame.reformat(width=width, height=height, format=pixel_format))

  def to_bytes(self) -> bytes: return self.to_ndarray().tobytes("C")

  @staticmethod
  def from_image(image): return VideoFrame(av.VideoFrame.from_image(image))

  @staticmethod
  def from_ndarray(array: np.ndarray, format: str): return VideoFrame(av.VideoFrame.from_ndarray(array, format))

  @staticmethod
  def from_buffer(buf: ByteString, width: int, height: int, format: str): return VideoFrame.from_ndarray(video_buffer_to_ndarray(buf, width, height), format)

@dataclass
class VideoReformatterInfo:
  frame_rate: float | int
  pixel_format: str
  width: int
  height: int

  @property
  def time_base(self): return Fraction(1, int(self.frame_rate)) if int(self.frame_rate) == self.frame_rate else Fraction(1 / self.frame_rate)

  def to_av_format(self) -> av.VideoFormat:
    return av.VideoFormat(self.pixel_format, self.width, self.height)

class VideoCodecInfo(CodecInfo[VideoFrame]):
  def __init__(self, width: int, height: int, frame_rate: float | int, pixel_format: str, codec: str, options: dict[str, Any] = {}):
    super().__init__(codec)
    self.frame_rate = frame_rate
    self.width = width
    self.height = height
    self.options = options
    self.pixel_format = pixel_format

  def to_av_format(self) -> av.VideoFormat:
    return av.VideoFormat(self.pixel_format, self.width, self.height)

  @property
  def type(self): return 'video'

  @property
  def rate(self): return self.frame_rate

  @property
  def reformatter_info(self): return VideoReformatterInfo(self.frame_rate, self.pixel_format, self.width, self.height)

  @cached_property
  def codec_id(self):
    try: return av.Codec(self.codec, "r").id
    except: pass
    try: return av.Codec(self.codec, "w").id
    except: pass
    raise ValueError("Codec not found!")

  def get_reformatter(self, from_codec: 'VideoCodecInfo') -> Reformatter: return VideoReformatter(self.reformatter_info, from_codec.reformatter_info)

  def compatible_with(self, other: 'CodecInfo') -> bool:
    if not isinstance(other, VideoCodecInfo): return False
    return self.codec_id == other.codec_id and self.frame_rate == other.frame_rate and self.width == other.width and self.height == other.height and self.pixel_format == other.pixel_format

  def _get_av_codec_context(self, mode: Literal["w", "w"]):
    if mode not in ('r', 'w'): raise ValueError(f'Invalid mode: {mode}. Must be "r" or "w".')
    ctx: av.video.codeccontext.VideoCodecContext = av.video.codeccontext.VideoCodecContext.create(self.codec, mode)
    ctx.format = self.to_av_format()
    ctx.framerate = self.frame_rate
    ctx.options.update(self.options)

    ctx.thread_type = "FRAME"
    if "threads" in self.options: ctx.thread_count = int(self.options["threads"])
    if "bit_rate" in self.options: ctx.bit_rate = int(self.options["bit_rate"])
    if "bit_rate_tolerance" in self.options: ctx.bit_rate_tolerance = int(self.options["bit_rate_tolerance"])
    if mode == "w": ctx.time_base = self.time_base
    return ctx

  @staticmethod
  def from_codec_context(ctx: av.video.codeccontext.VideoCodecContext):
    format = ctx.format
    framerate = float(ctx.rate)
    return VideoCodecInfo(ctx.width, ctx.height, framerate, format.name, ctx.name, options_from_codec_context(ctx))

def copy_av_video_frame(frame: av.VideoFrame) -> av.VideoFrame:
  new_frame = av.VideoFrame(frame.width, frame.height, frame.format.name)
  new_frame.time_base = frame.time_base
  new_frame.pts = frame.pts
  new_frame.dts = frame.dts
  new_frame.pict_type = frame.pict_type
  new_frame.colorspace = frame.colorspace
  new_frame.color_range = frame.color_range
  assert len(frame.planes) == len(new_frame.planes)
  for a, b in zip(new_frame.planes, frame.planes):
    ctypes.memmove(a.buffer_ptr, b.buffer_ptr, min(a.buffer_size, b.buffer_size))
  return new_frame

class FrameReformatter:
  def __init__(self, **kwargs) -> None:
    self.reformatter = av.video.reformatter.VideoReformatter()
    self.kwargs = kwargs

  def reformat(self, frame: VideoFrame):
    return VideoFrame(self.reformatter.reformat(frame.frame, **self.kwargs))

class VideoReformatter(Reformatter[VideoFrame]):
  def __init__(self, to_codec: VideoReformatterInfo, from_codec: VideoReformatterInfo) -> None:
    super().__init__()
    self.to_codec = to_codec
    self.from_codec = from_codec
    self.reformatter = av.video.reformatter.VideoReformatter()
    self.frame_duation = Fraction(to_codec.frame_rate / from_codec.frame_rate)
    self.rel_frame_counter = Fraction(0)
    self.min_pts = -2**31

  async def reformat(self, frame: VideoFrame) -> list[VideoFrame]:
    self.rel_frame_counter += self.frame_duation
    frame_count = int(self.rel_frame_counter)
    self.rel_frame_counter -= frame_count
    if frame_count == 0: return []

    assert frame.frame.width == self.from_codec.width
    assert frame.frame.height == self.from_codec.height
    assert frame.frame.format.name == self.from_codec.pixel_format

    out_frame = self.reformatter.reformat(frame.frame, width=self.to_codec.width, height=self.to_codec.height, format=self.to_codec.pixel_format)
    time_base = frame.frame.time_base if frame.frame.time_base is not None else self.from_codec.time_base

    pts = max(int((time_base * frame.frame.pts) * self.to_codec.frame_rate), self.min_pts)
    self.min_pts = pts + frame_count

    frames: list[VideoFrame] = []
    for i in range(frame_count):
      new_frame = out_frame if i == frame_count - 1 else copy_av_video_frame(out_frame)
      new_frame.pts = pts + i
      new_frame.dts = pts + i
      new_frame.time_base = self.to_codec.time_base
      frames.append(VideoFrame(new_frame))

    return frames
