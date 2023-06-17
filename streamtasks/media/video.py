from typing import Optional
import asyncio
import av
import numpy as np
import time
from fractions import Fraction
from streamtasks.media.config import *
from streamtasks.media.types import MediaPacket

class VideoCodecInfo:
  width: int
  height: int
  framerate: float
  bitrate: Optional[int] = None
  pixel_format: str
  encoding: str
  crf: Optional[int] = None

  def __init__(self, width: int, height: int, framerate: int, pixel_format: str = 'yuv420p', 
                encoding: str = 'h264', bitrate: Optional[int] = None, crf: Optional[int] = None):
    self.width = width
    self.height = height
    self.framerate = framerate
    self.bitrate = bitrate
    self.pixel_format = pixel_format
    self.encoding = encoding
    self.crf = crf

  def to_av_format(self) -> av.video.format.VideoFormat:
    return av.video.format.VideoFormat(self.pixel_format, self.width, self.height)

  def get_av_encoder(self): return self._get_av_codec_context('w')
  def get_av_decoder(self): return self._get_av_codec_context('r')
  def _get_av_codec_context(self, mode: str):
    assert mode in ('r', 'w'), f'Invalid mode: {mode}. Must be "r" or "w".' 
    ctx = av.codec.CodecContext.create(self.encoding, mode)
    ctx.format = self.to_av_format()
    ctx.framerate = self.framerate
    ctx.thread_type = 'AUTO'

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
    return VideoCodecInfo(format.width, format.height, ctx.framerate, format.name, ctx.name, ctx.bit_rate, ctx.options.get('crf', None))

class VideoFrame:
  def __init__(self, frame: av.video.frame.VideoFrame):
    self.frame = frame

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


class VideoDecoder:
  def __init__(self, codec_info: VideoCodecInfo):
    self.codec_info = codec_info
    self.codec_context = codec_info.get_av_decoder()

  async def decode(self, packet: MediaPacket) -> Optional[VideoFrame]:
    loop = asyncio.get_running_loop()
    av_packet = packet.to_av_packet()
    frames = await loop.run_in_executor(None, self._decode, av_packet)
    return [ VideoFrame(frame) for frame in frames]

  def _decode(self, packet: av.Packet):
    return self.codec_context.decode(packet)

class VideoEncoder:
  _t0: int = 0

  def __init__(self, codec_info: VideoCodecInfo):
    self.codec_info = codec_info
    self.codec_context = codec_info.get_av_encoder()

  async def encode(self, frame: VideoFrame) -> list[MediaPacket]:
    loop = asyncio.get_running_loop()
    av_frame = frame.frame
    packets = await loop.run_in_executor(None, self._encode, av_frame)

    if len(packets) == 0: return []

    if self._t0 == 0:
      self._t0 = int(time.time() * 1000 - (packets[0].pts / DEFAULT_TIME_BASE_TO_MS))
    
    return [ MediaPacket.from_av_packet(packet, self._t0) for packet in packets ]

  def _encode(self, frame: av.video.frame.VideoFrame):
    return self.codec_context.encode(frame)