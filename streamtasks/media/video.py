from fractions import Fraction
from typing import Literal, Optional
import av
import numpy as np
from streamtasks.media.codec import CodecInfo, Frame

class VideoFrame(Frame[av.video.frame.VideoFrame]):
  def to_rgb(self):
    return VideoFrame(self.frame.to_rgb())

  def to_ndarray(self):
    return self.frame.to_ndarray()
  
  def convert(self, width: int | None = None, height: int | None = None, pixel_format: str | None = None) -> np.ndarray:
    return self.frame.reformat(width=width, height=height, format=pixel_format).to_ndarray()

  @staticmethod
  def from_image(image): return VideoFrame(av.video.frame.VideoFrame.from_image(image))

  @staticmethod
  def from_ndarray(array: np.ndarray, format: str): return VideoFrame(av.video.frame.VideoFrame.from_ndarray(array, format))

class VideoCodecInfo(CodecInfo[VideoFrame]):
  width: int
  height: int
  bitrate: Optional[int] = None
  pixel_format: str
  crf: Optional[int] = None

  def __init__(self, width: int, height: int, frame_rate: int, pixel_format: str = 'yuv420p',
               codec: str = 'h264', bitrate: Optional[int] = None, crf: Optional[int] = None):
    super().__init__(codec)
    self.frame_rate = frame_rate
    self.width = width
    self.height = height
    self.bitrate = bitrate
    self.pixel_format = pixel_format
    self.crf = crf

  def to_av_format(self) -> av.video.format.VideoFormat:
    return av.video.format.VideoFormat(self.pixel_format, self.width, self.height)

  @property
  def type(self): return 'video'

  @property
  def rate(self): return self.frame_rate
  
  @property
  def options(self) -> dict[str, str]: return {}

  def compatible_with(self, other: 'CodecInfo') -> bool:
    if not isinstance(other, VideoCodecInfo): return False
    return self.codec == other.codec and self.pixel_format == other.pixel_format and self.frame_rate == other.frame_rate and self.width == other.width and self.height == other.height

  def _get_av_codec_context(self, mode: Literal["w", "w"]):
    if mode not in ('r', 'w'): raise ValueError(f'Invalid mode: {mode}. Must be "r" or "w".')
    ctx = av.codec.CodecContext.create(self.codec, mode)
    ctx.format = self.to_av_format()
    ctx.framerate = self.frame_rate
    
    if mode == "w":
      ctx.time_base = self.time_base
      if self.crf is not None:
        ctx.options['crf'] = str(self.crf)
      if self.bitrate is not None:
        ctx.bit_rate = self.bitrate
    return ctx

  @staticmethod
  def from_codec_context(ctx: av.codec.CodecContext):
    format = ctx.format
    return VideoCodecInfo(ctx.width, ctx.height, ctx.framerate, format.name, ctx.name, ctx.bit_rate, ctx.options.get('crf', None))
