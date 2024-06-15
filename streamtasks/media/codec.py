from abc import ABC, abstractmethod
from fractions import Fraction
from typing import Any, ByteString, Iterable, Literal, Self, TypeVar, Generic
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

  @property
  def dtime(self):
    if self.frame.time_base is None or self.frame.dts is None: return None
    else: return self.frame.time_base * self.frame.dts

  def set_ts(self, time: Fraction, time_base: Fraction):
    ts = int(time / time_base)
    self.frame.time_base = time_base
    self.frame.dts = ts
    self.frame.pts = ts

  @abstractmethod
  def to_bytes(self) -> ByteString: pass

  @staticmethod
  def from_av_frame(av_frame: Any) -> 'Frame[T]':
    if isinstance(av_frame, av.VideoFrame):
      from streamtasks.media.video import VideoFrame
      return VideoFrame(av_frame)
    elif isinstance(av_frame, av.AudioFrame):
      from streamtasks.media.audio import AudioFrame
      return AudioFrame(av_frame)

F = TypeVar('F', bound=Frame)


class Encoder(Generic[F]):
  def __init__(self, codec_info: 'CodecInfo[F]'):
    self.codec_info = codec_info
    self.codec_context = codec_info._get_av_codec_context("w")
    self.time_base = codec_info.time_base

  def __del__(self): self.close()

  async def encode(self, frame: F) -> list[MediaPacket]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, self.encode_sync, frame)

  async def flush(self) -> list[MediaPacket]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, self.flush_sync)

  def encode_sync(self, frame: F): return self._encode(frame)
  def flush_sync(self): return self._encode(None)

  def close(self): self.codec_context.close(strict=False)
  def _encode(self, frame: F | None): return [ MediaPacket.from_av_packet(packet, self.time_base) for packet in self.codec_context.encode(None if frame is None else frame.frame) ]


class Decoder(Generic[F]):
  def __init__(self, codec_info: 'CodecInfo[F]', codec_context: av.codec.context.CodecContext | None = None):
    self.codec_info = codec_info
    self.codec_context = codec_context or codec_info._get_av_codec_context("r")
    self.time_base = codec_info.time_base

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

class Reformatter(Generic[F]):
  async def reformat(self, frame: F) -> list[F]: pass
  async def reformat_all(self, frames: list[F]):
    out_frames: list[F] = []
    for frame in frames: out_frames.extend(await self.reformat(frame))
    return out_frames

class Transcoder(ABC):
  @abstractmethod
  async def transcode(self, packet: MediaPacket) -> list[MediaPacket]: pass
  @abstractmethod
  async def flush(self) -> list[MediaPacket]: pass

class AVTranscoder(Transcoder):
  def __init__(self, decoder: Decoder, encoder: Encoder):
    self.decoder = decoder
    self.encoder = encoder
    self.reformatter = encoder.codec_info.get_reformatter(decoder.codec_info)

    self._flushed = False
    self._frame_lo: Fraction = Fraction()

  @property
  def flushed(self): return self._flushed

  async def transcode(self, packet: MediaPacket) -> list[MediaPacket]:
    self._flushed = False
    packets = await self._encode_frames(await self.decoder.decode(packet))
    return packets

  async def flush(self):
    packets = await self._encode_frames(await self.decoder.flush())
    for packet in await self.encoder.flush(): packets.append(packet)
    self._flushed = True
    return packets

  async def _encode_frames(self, frames: Iterable[Frame]):
    packets: list[MediaPacket] = []
    for frame in await self.reformatter.reformat_all(frames):
      packets.extend(await self.encoder.encode(frame))
    return packets

class CodecInfo(ABC, Generic[F]):
  def __init__(self, codec: str):
    self.codec = codec

  @property
  @abstractmethod
  def type(self) -> Literal["video", "audio"]: pass

  @property
  @abstractmethod
  def rate(self) -> float | int: pass

  @property
  def time_base(self): return Fraction(1, int(self.rate)) if self.rate == int(self.rate) else Fraction(1/self.rate)

  @abstractmethod
  def compatible_with(self, other: 'CodecInfo') -> bool: pass

  @abstractmethod
  def get_reformatter(self, from_codec: Self) -> Reformatter: pass

  @abstractmethod
  def _get_av_codec_context(self, mode: str) -> av.codec.CodecContext: pass

  def get_encoder(self) -> Encoder: return Encoder[F](self)
  def get_decoder(self) -> Decoder: return Decoder[F](self)
  def get_transcoder(self, to: 'CodecInfo') -> Transcoder:
    return AVTranscoder(self.get_decoder(), to.get_encoder())

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
