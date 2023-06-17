from typing import Optional
from streamtasks.media.config import *
from streamtasks.media.types import MediaPacket
import numpy as np
import time
import asyncio
import av

class AudioCodecInfo:
  codec: str
  channels: int # NOTE: may be insufficient
  sample_rate: int
  sample_format: str # NOTE: may be insufficient
  bitrate: Optional[int]
  crf: Optional[int]

  def __init__(self, codec: str, channels: int, sample_rate: int, sample_format: str, bitrate: Optional[int], crf: Optional[int] = None):
    self.codec = codec
    self.bitrate = bitrate
    self.channels = channels
    self.sample_rate = sample_rate
    self.sample_format = sample_format
    self.crf = crf

  def to_av_format(self):
    return av.audio.format.AudioFormat(self.sample_format)

  def to_av_layout(self):
    return av.audio.layout.AudioLayout(self.channels)

  def get_av_encoder(self): return self._get_av_codec_context('w')
  def get_av_decoder(self): return self._get_av_codec_context('r')
  def _get_av_codec_context(self, mode: str):
    assert mode in ('r', 'w'), f'Invalid mode: {mode}. Must be "r" or "w".'
    ctx = av.codec.CodecContext.create(self.codec, mode)
    ctx.format = self.to_av_format()
    ctx.layout = self.to_av_layout()
    ctx.sample_rate = self.sample_rate

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
    layout = ctx.layout
    return AudioCodecInfo(ctx.name, ctx.channels, ctx.sample_rate, ctx.frame_size, format.name, ctx.bit_rate, ctx.options.get('crf', None))

class AudioFrame:
  def __init__(self, frame: av.audio.frame.AudioFrame):
    self.frame = frame

  def to_ndarray(self):
    return self.frame.to_ndarray()

  @staticmethod
  def from_ndarray(ndarray: np.ndarray, sample_format: str, layout: str):
    return AudioFrame(av.audio.frame.AudioFrame.from_ndarray(ndarray, sample_format, layout))

class AudioDecoder:
  codec_info: VideoCodecInfo
  codec_context: av.audio.codeccontext.AudioCodecContext

  def __init__(self, codec_info: AudioCodecInfo):
    self.codec_info = codec_info
    self.codec_context = codec_info.get_av_decoder()

  async def decode(self, packet: MediaPacket) -> list[AudioFrame]:
    loop = asyncio.get_running_loop()
    av_packet = packet.to_av_packet()
    frames = await loop.run_in_executor(None, self._decode, av_packet)
    return [ AudioFrame(frame) for frame in frames ]

  def _decode(self, packet: av.packet.Packet): return self.codec_context.decode(packet)
  def close(self): self.codec_context.close()

class AudioEncoder:
  _t0: int = 0
  codec_info: VideoCodecInfo
  codec_context: av.audio.codeccontext.AudioCodecContext

  def __init__(self, codec_info: AudioCodecInfo):
    self.codec_info = codec_info
    self.codec_context = codec_info.get_av_encoder()
    self._t0 = 0

  async def encode(self, frame: AudioFrame) -> list[MediaPacket]:
    loop = asyncio.get_running_loop()
    av_frame = frame.frame
    packets = await loop.run_in_executor(None, self._encode, av_frame)
    
    if len(packets) == 0: return []

    if self._t0 == 0:
      self._t0 = int(time.time() * 1000 - (packets[0].pts / DEFAULT_TIME_BASE_TO_MS))

    return [ MediaPacket.from_av_packet(packet, self._t0) for packet in packets ]

  def _encode(self, frame: AudioFrame):
    return self.codec_context.encode(frame.frame)

  def close(self): self.codec_context.close()