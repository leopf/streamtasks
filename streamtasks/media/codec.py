from abc import ABC, abstractmethod
from typing import Any, TypeVar, TypedDict, Optional, Generic
from streamtasks.media.types import MediaPacket
from streamtasks.media.config import *
from dataclasses import dataclass 
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

class CodecOptions(TypedDict):
  thread_type: Optional[str]

  def apply(ctx: av.codec.CodecContext, opt: CodecOptions):
    ctx.thread_type = opt['thread_type'] if "thread_type" in opt else "AUTO"

class CodecInfo(ABC, Generic[F]):
  codec: str

  def __init__(self, codec: str):
    self.codec = codec

  @abstractmethod
  def _get_av_codec_context(self, mode: str) -> av.codec.CodecContext: pass
  def _get_av_codec_context_with_options(self, mode: str, options: CodecOptions) -> av.codec.CodecContext:
    ctx = self._get_av_codec_context(mode)
    CodecOptions.apply(ctx, options)
    return ctx

  def get_encoder(self, options: CodecOptions = {}) -> Encoder: return Encoder[F](self._get_av_codec_context_with_options("w", options))
  def get_decoder(self, options: CodecOptions = {}) -> Decoder: return Decoder[F](self._get_av_codec_context_with_options("r", options))
  def get_transcoder(self, to: CodecInfo, options: CodecOptions = {}) -> Transcoder: return Transcoder(self.get_decoder(options), to.get_encoder(options))