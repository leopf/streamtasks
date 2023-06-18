import av
import asyncio
import time
from streamtasks.media.config import *
from streamtasks.media.codec import CodecInfo, Frame
from streamtasks.media.types import MediaPacket
from av.subtitles.subtitle import SubtitleSet
from typing import Any

class SubtitleCodecInfo(CodecInfo):
  @property
  def type(self): return 'subtitle'
  
  def _get_av_codec_context(self, mode: str):
    assert mode in ('r', 'w'), f'Invalid mode: {mode}. Must be "r" or "w".'
    ctx = av.codec.CodecContext.create(self.codec, mode)
    return ctx

  def compatible_with(self, other: 'CodecInfo') -> bool:
    if not isinstance(other, SubtitleCodecInfo): return False
    return self.codec == other.codec

  @staticmethod
  def from_codec_context(ctx: av.codec.CodecContext):
    return SubtitleCodecInfo(ctx.name)

class SubtitleFrame(Frame[SubtitleSet]):
  pass