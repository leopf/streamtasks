import av
from streamtasks.media.config import *
from streamtasks.media.codec import CodecInfo, Frame
from av.subtitles.subtitle import SubtitleSet

class SubtitleCodecInfo(CodecInfo):
  @property
  def type(self): return 'subtitle'
  
  def _get_av_codec_context(self, mode: str):
    if mode not in ('r', 'w'): raise ValueError(f'Invalid mode: {mode}. Must be "r" or "w".')
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