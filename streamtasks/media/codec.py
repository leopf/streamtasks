from abc import ABC, abstractmethod
from typing import Any, TypeVar
from streamtasks.media.types import MediaPacket
from streamtasks.media.config import *
import av
import asyncio

T = TypeVar('T')
class Frame(ABC, Generic[T]):
  frame: T

  def __init__(self, frame: T):
    self.frame = frame

F = TypeVar('F', bound=Frame)
class Encoder(Generic[F]):
  _t0: int = 0
  codec_context: av.codec.CodecContext

  def __init__(self, codec_context: av.codec.CodecContext):
    self.codec_context = codec_context
    self._t0 = 0
  def __del__(self): self.close()
  
  async def encode(self, data: Any) -> list[MediaPacket]:
    loop = asyncio.get_running_loop()
    packets = await loop.run_in_executor(None, self._encode, data)

    if len(packets) == 0: return []
    if self._t0 == 0: self._t0 = int(time.time() * 1000 - (packets[0].pts / DEFAULT_TIME_BASE_TO_MS))

    return [ MediaPacket.from_av_packet(packet, self._t0) for packet in packets ]

  def close(self): self.codec_context.close()
  def _encode(self, frame: F) -> list[av.Packet]: return self.codec_context.encode(frame.frame)

class Decoder(Generic[F]):
  codec_context: av.codec.CodecContext

  def __init__(self, codec_context: av.codec.CodecContext):
    self.codec_context = codec_context

  async def decode(self, packet: MediaPacket) -> list[F]:
    loop = asyncio.get_running_loop()
    av_packet = packet.to_av_packet()
    frames = await loop.run_in_executor(None, self._decode, av_packet)
    return [ F(frame) for frame in frames ]

  def close(self): self.codec_context.close()
  def _decode(self, packet: av.packet.Packet) -> list[F]: return self.codec_context.decode(packet)

class Transcoder:
  def __init__(self, decoder: Decoder, encoder: Encoder):
    self.decoder = decoder
    self.encoder = encoder

  async def transcode(self, packet: MediaPacket) -> list[MediaPacket]:
    frames = await self.decoder.decode(packet)
    return await self.encode(frames)

class CodecInfo(ABC, Generic[F]):
  @abstractmethod
  def get_av_codec_context(self) -> av.codec.CodecContext: pass

  def get_encoder(self) -> Encoder: return Encoder[F](self.get_av_codec_context())
  def get_decoder(self) -> Decoder: return Decoder[F](self.get_av_codec_context())
  def get_transcoder(self, to: CodecInfo) -> Transcoder: return Transcoder(self.get_decoder(), to.get_encoder())