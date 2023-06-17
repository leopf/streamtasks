import av
import asyncio
import time
from streamtasks.media.config import *
from streamtasks.media.types import MediaPacket

class SubtitleCodecInfo:
  codec: str

  def __init__(self, codec: str):
    self.codec = codec

  def get_av_encoder(self): return self._get_av_codec_context('w')
  def get_av_decoder(self): return self._get_av_codec_context('r')
  def _get_av_codec_context(self, mode: str):
    assert mode in ('r', 'w'), f'Invalid mode: {mode}. Must be "r" or "w".'
    ctx = av.codec.CodecContext.create(self.codec, mode)
    ctx.thread_type = 'AUTO'
    return ctx

  @staticmethod
  def from_codec_context(ctx: av.codec.CodecContext):
    return SubtitleCodecInfo(ctx.name)

class SubtitleFrame:
  def __init__(self, frame: av.subtitle.subtitle.SubtitleSet):
    self.subtitle_set = frame

class SubtitleDecoder:
  codec_info: SubtitleCodecInfo
  codec_ctx: av.subtitles.codeccontext.SubtitleCodecContext

  def __init__(self, codec_info: SubtitleCodecInfo):
    self.codec_info = codec_info
    self.codec_ctx = codec_info.get_av_decoder()

  async def decode(self, packet: MediaPacket):
    loop = asyncio.get_running_loop()
    av_packet = packet.to_av_packet()
    frames = await loop.run_in_executor(None, self._decode, av_packet)
    return [ SubtitleFrame(frame) for frame in frames ]

  def _decode(self, packet: av.packet.Packet): return self.codec_context.decode(packet)
  def close(self): self.codec_context.close()

class SubtitleEncoder:
  _t0: int = 0
  codec_info: SubtitleCodecInfo
  codec_ctx: av.subtitles.codeccontext.SubtitleCodecContext

  def __init__(self, codec_info: SubtitleCodecInfo):
    self.codec_info = codec_info
    self.codec_ctx = codec_info.get_av_encoder()
    self._t0 = 0

  async def encode(self, frame: SubtitleFrame) -> list[MediaPacket]:
    loop = asyncio.get_running_loop()
    av_frame = frame.subtitle_set
    packets = await loop.run_in_executor(None, self._encode, av_frame)

    if len(packets) == 0: return []

    if self._t0 == 0:
      self._t0 = int(time.time() * 1000 - (packets[0].pts / DEFAULT_TIME_BASE_TO_MS))

    return [ MediaPacket.from_av_packet(packet, self._t0) for packet in packets ]

  def _encode(self, frame: av.subtitle.subtitle.SubtitleSet): return self.codec_context.encode(frame)
  def close(self): self.codec_context.close()
