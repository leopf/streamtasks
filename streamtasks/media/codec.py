from abc import ABC, abstractmethod
from fractions import Fraction
from typing import Any, Iterable, TypeVar, TypedDict, Optional, Generic
import av.codec
import av.frame
import av.video
from streamtasks.media.packet import MediaPacket
import av
import asyncio

T = TypeVar('T', bound=av.frame.Frame)

class Frame(ABC, Generic[T]):
  def __init__(self, frame: T):
    self.frame: T = frame

  def from_av_frame(av_frame: Any) -> 'Frame[T]':
    if isinstance(av_frame, av.VideoFrame):
      from streamtasks.media.video import VideoFrame
      return VideoFrame(av_frame)
    elif isinstance(av_frame, av.AudioFrame):
      from streamtasks.media.audio import AudioFrame
      return AudioFrame(av_frame)

F = TypeVar('F', bound=Frame)


class Encoder(Generic[F]):
  def __init__(self, codec_context: av.codec.CodecContext):
    self.codec_context = codec_context
  def __del__(self): self.close()

  async def encode(self, data: F) -> list[MediaPacket]:
    loop = asyncio.get_running_loop()
    packets = await loop.run_in_executor(None, self._encode, data.frame)
    return [ MediaPacket.from_av_packet(packet) for packet in packets ]

  async def flush(self) -> list[MediaPacket]:
    loop = asyncio.get_running_loop()
    packets = await loop.run_in_executor(None, self._encode, None)
    return [ MediaPacket.from_av_packet(packet) for packet in packets ]

  def close(self): self.codec_context.close(strict=False)
  def _encode(self, frame: F) -> list[av.Packet]: return self.codec_context.encode(frame)


class Decoder(Generic[F]):
  def __init__(self, codec_context: av.codec.CodecContext, time_base: Fraction | None):
    self.codec_context = codec_context
    self.time_base = time_base

  async def decode(self, packet: MediaPacket) -> list[F]:
    loop = asyncio.get_running_loop()
    av_packet = packet.to_av_packet(self.time_base)
    frames = await loop.run_in_executor(None, self._decode, av_packet)
    return [ Frame.from_av_frame(frame) for frame in frames ]

  async def flush(self):
    loop = asyncio.get_running_loop()
    frames = await loop.run_in_executor(None, self._decode, None)
    return [ Frame.from_av_frame(frame) for frame in frames ]

  def close(self): self.codec_context.close()
  def _decode(self, packet: av.packet.Packet) -> list[F]: return self.codec_context.decode(packet)


class Transcoder(ABC):
  @abstractmethod
  async def transcode(self, packet: MediaPacket) -> list[MediaPacket]: pass
  @abstractmethod
  async def flush(self) -> list[MediaPacket]: pass

class AVTranscoder(Transcoder):
  def __init__(self, decoder: Decoder, encoder: Encoder):
    self.decoder = decoder
    self.encoder = encoder
    self._flushed = False

  @property
  def flushed(self): return self._flushed
  
  async def transcode(self, packet: MediaPacket) -> list[MediaPacket]:
    self._flushed = False
    return await self._encode_frames(await self.decoder.decode(packet))
  
  async def flush(self):
    packets = await self._encode_frames(await self.decoder.flush())
    for packet in await self.encoder.flush(): packets.append(packet)
    self._flushed = True
    return packets

  async def _encode_frames(self, frames: Iterable[Frame]):
    packets: list[MediaPacket] = []
    for frame in frames: packets.extend(await self.encoder.encode(frame))
    return packets

class CodecInfo(ABC, Generic[F]):
  def __init__(self, codec: str):
    self.codec = codec

  @property
  @abstractmethod
  def type(self) -> str: pass

  @property
  def rate(self) -> Optional[float]: return None

  @property
  def time_base(self): 
    if self.rate is None: return None
    return Fraction(1, int(self.rate)) if self.rate == int(self.rate) else Fraction(1/self.rate)

  @abstractmethod
  def compatible_with(self, other: 'CodecInfo') -> bool: pass

  @abstractmethod
  def _get_av_codec_context(self, mode: str) -> av.codec.CodecContext: pass

  def get_encoder(self) -> Encoder: return Encoder[F](self._get_av_codec_context("w"))
  def get_decoder(self) -> Decoder: return Decoder[F](self._get_av_codec_context("r"), self.time_base)
  def get_transcoder(self, to: 'CodecInfo') -> Transcoder: return AVTranscoder(self.get_decoder(), to.get_encoder())

  @staticmethod
  def from_codec_context(ctx: av.codec.CodecContext) -> 'CodecInfo':
    if ctx.type == 'video':
      from streamtasks.media.video import VideoCodecInfo
      return VideoCodecInfo.from_codec_context(ctx)
    elif ctx.type == 'audio':
      from streamtasks.media.audio import AudioCodecInfo
      return AudioCodecInfo.from_codec_context(ctx)
    else:
      raise ValueError(f'Invalid codec type: {ctx.type}')