from typing import Optional
import asyncio
import av
import numpy as np
import time
from fractions import Fraction
from streamtasks.media.config import *
from streamtasks.message import MediaPacket
from streamtasks.media.codec import CodecInfo, Frame

class VideoFrame(Frame[av.video.frame.VideoFrame]):
  def to_image(self):
    return self.frame.to_image()

  def to_rgb(self):
    return VideoFrame(self.frame.to_rgb())

  def to_ndarray(self):
    return self.frame.to_ndarray()

  @staticmethod
  def from_image(image): return VideoFrame(av.video.frame.VideoFrame.from_image(image))

  @staticmethod
  def from_ndarray(array: np.ndarray, format: str): return VideoFrame(av.video.frame.VideoFrame.from_ndarray(array))

class VideoCodecInfoMinimal(CodecInfo[VideoFrame]):
  framerate: float

  def __init__(self, codec: str, framerate: float):
    super().__init__(codec)
    self.framerate = framerate

  def _get_av_codec_context(self, mode: str): raise NotImplementedError("VideoCodecInfoMinimal does not have all the info.")

class VideoCodecInfo(VideoCodecInfoMinimal):
  width: int
  height: int
  bitrate: Optional[int] = None
  pixel_format: str
  crf: Optional[int] = None

  def __init__(self, width: int, height: int, framerate: int, pixel_format: str = 'yuv420p', 
                codec: str = 'h264', bitrate: Optional[int] = None, crf: Optional[int] = None):
    super().__init__(codec, framerate)
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
  def rate(self) -> Optional[int]: self.framerate

  def compatible_with(self, other: 'CodecInfo') -> bool:
    if not isinstance(other, VideoCodecInfo): return False
    return self.codec == other.codec and self.pixel_format == other.pixel_format and self.framerate == other.framerate and self.width == other.width and self.height == other.height

  def _get_av_codec_context(self, mode: str):
    assert mode in ('r', 'w'), f'Invalid mode: {mode}. Must be "r" or "w".' 
    ctx = av.codec.CodecContext.create(self.codec, mode)
    ctx.format = self.to_av_format()
    ctx.framerate = self.framerate

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
    return VideoCodecInfo(ctx.width, ctx.height, ctx.framerate, format.name, ctx.name, ctx.bit_rate, ctx.options.get('crf', None))
