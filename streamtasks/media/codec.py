from abc import ABC, abstractmethod
from typing import Any, TypeVar, TypedDict, Optional, Generic
from streamtasks.media.packet import MediaPacket
import av
import time
import asyncio

T = TypeVar('T')

class Frame(ABC, Generic[T]):
  frame: T

  def __init__(self, frame: T):
    self.frame = frame

  def from_av_frame(av_frame: Any) -> 'Frame[T]':
    if isinstance(av_frame, av.video.frame.VideoFrame):
      from streamtasks.media.video import VideoFrame
      return VideoFrame(av_frame)
    elif isinstance(av_frame, av.audio.frame.AudioFrame):
      from streamtasks.media.audio import AudioFrame
      return AudioFrame(av_frame)
    elif isinstance(av_frame, av.subtitles.subtitle.SubtitleSet):
      from streamtasks.media.subtitle import SubtitleFrame
      return SubtitleFrame(av_frame)


F = TypeVar('F', bound=Frame)


class Encoder(Generic[F]):
  codec_context: av.codec.CodecContext

  def __init__(self, codec_context: av.codec.CodecContext):
    self.codec_context = codec_context
  def __del__(self): self.close()

  async def encode(self, data: Any) -> list[MediaPacket]:
    loop = asyncio.get_running_loop()
    packets = await loop.run_in_executor(None, self._encode, data)

    if len(packets) == 0: return []

    return [ MediaPacket.from_av_packet(packet) for packet in packets ]

  def close(self): self.codec_context.close(strict=False)
  def _encode(self, frame: F) -> list[av.Packet]: return self.codec_context.encode(frame.frame)


class Decoder(Generic[F]):
  codec_context: av.codec.CodecContext

  def __init__(self, codec_context: av.codec.CodecContext):
    self.codec_context = codec_context

  async def decode(self, packet: MediaPacket) -> list[F]:
    loop = asyncio.get_running_loop()
    av_packet = packet.to_av_packet()
    frames = await loop.run_in_executor(None, self._decode, av_packet)
    return [ Frame.from_av_frame(frame) for frame in frames ]

  def close(self): self.codec_context.close()
  def _decode(self, packet: av.packet.Packet) -> list[F]: return self.codec_context.decode(packet)


class Transcoder(ABC):
  @abstractmethod
  async def transcode(self, packet: MediaPacket) -> list[MediaPacket]: pass


class AVTranscoder:
  def __init__(self, decoder: Decoder, encoder: Encoder):
    self.decoder = decoder
    self.encoder = encoder

  async def transcode(self, packet: MediaPacket) -> list[MediaPacket]:
    frames = await self.decoder.decode(packet)
    packets = []
    for frame in frames:
      packets += await self.encoder.encode(frame)
    return packets


class EmptyTranscoder:
  async def transcode(self, packet: MediaPacket) -> list[MediaPacket]: return [ packet ]


class CodecOptions(TypedDict):
  thread_type: Optional[str]


def apply_codec_options(ctx: av.codec.CodecContext, opt: 'CodecOptions'):
  ctx.thread_type = opt['thread_type'] if "thread_type" in opt else "AUTO"


class CodecInfo(ABC, Generic[F]):
  codec: str

  def __init__(self, codec: str):
    self.codec = codec

  @property
  @abstractmethod
  def type(self) -> str: pass

  @property
  def rate(self) -> Optional[int]: return None

  @abstractmethod
  def compatible_with(self, other: 'CodecInfo') -> bool: pass

  @abstractmethod
  def _get_av_codec_context(self, mode: str) -> av.codec.CodecContext: pass
  def _get_av_codec_context_with_options(self, mode: str, options: CodecOptions) -> av.codec.CodecContext:
    ctx = self._get_av_codec_context(mode)
    apply_codec_options(ctx, options)
    return ctx

  def get_encoder(self, options: CodecOptions = {}) -> Encoder: return Encoder[F](self._get_av_codec_context_with_options("w", options))
  def get_decoder(self, options: CodecOptions = {}) -> Decoder: return Decoder[F](self._get_av_codec_context_with_options("r", options))
  def get_transcoder(self, to: 'CodecInfo', options: CodecOptions = {}) -> Transcoder: return AVTranscoder(self.get_decoder(options), to.get_encoder(options))

  @staticmethod
  def from_codec_context(ctx: av.codec.CodecContext) -> 'CodecInfo':
    from streamtasks.media.video import VideoCodecInfo
    from streamtasks.media.audio import AudioCodecInfo
    from streamtasks.media.subtitle import SubtitleCodecInfo

    if ctx.type == 'video':
      return VideoCodecInfo.from_codec_context(ctx)
    elif ctx.type == 'audio':
      return AudioCodecInfo.from_codec_context(ctx)
    elif ctx.type == 'subtitle':
      return SubtitleCodecInfo.from_codec_context(ctx)
    else:
      raise ValueError(f'Invalid codec type: {ctx.type}')