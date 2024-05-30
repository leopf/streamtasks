from typing import Literal
from streamtasks.media.util import list_pixel_formats, list_sample_formats, list_sorted_available_codecs
from streamtasks.system.configurators import EditorFields

class MediaEditorFields:
  def pixel_format(key: str = "pixel_format", label: str | None = None, allowed_values: set[str] | None = None):
    return EditorFields.select(key=key, label=label,
      items=[ (pxl_fmt, pxl_fmt.upper()) for pxl_fmt in list_pixel_formats() if allowed_values is None or pxl_fmt in allowed_values])

  def codec_name(mode: Literal["w", "r"], codec_type: str, key: str = "codec", label: str | None = None):
    return EditorFields.select(key=key, label=label,
      items=[ (codec.coder_name, codec.coder_name.upper()) for codec in list_sorted_available_codecs(mode) if codec.type == codec_type])

  def codec(mode: Literal["w", "w"], codec_type: str, codec_key: str = "codec", coder_key: str = "coder"):
    return EditorFields.multiselect([ { codec_key: codec.codec_name, coder_key: codec.coder_name } for codec in list_sorted_available_codecs(mode) if codec.type == codec_type ])

  def video_codec(mode: Literal["w", "w"], codec_key: str = "codec", coder_key: str = "coder"):
    return MediaEditorFields.codec(mode, "video", codec_key=codec_key, coder_key=coder_key)

  def audio_codec(mode: Literal["w", "w"], codec_key: str = "codec", coder_key: str = "coder"):
    return MediaEditorFields.codec(mode, "audio", codec_key=codec_key, coder_key=coder_key)

  def video_codec_name(mode: Literal["w", "r"], key: str = "codec", label: str | None = None):
    return MediaEditorFields.codec_name(mode=mode, key=key, codec_type="video", label=label)

  def audio_codec_name(mode: Literal["w", "r"], key: str = "codec", label: str | None = None):
    return MediaEditorFields.codec_name(mode=mode, key=key, codec_type="audio", label=label)

  def pixel_size(key: str, label: str | None = None):
    return EditorFields.integer(key=key, label=label, min_value=0, unit="px")

  def rate(unit: str, key: str = "rate", label: str | None = None, is_int: bool = False):
    return EditorFields.number(key=key, label=label, unit=unit, min_value=0, is_int=is_int)

  def channel_count(key: str = "channels", label: str | None = None):
    return EditorFields.integer(key=key, label=label, min_value=1, max_value=16)

  def sample_format(key: str = "sample_format", label: str | None = None, allowed_values: set[str] | None = None):
    return EditorFields.select(key=key, label=label,
      items=[ (sample_fmt, sample_fmt.upper()) for sample_fmt in list_sample_formats() if allowed_values is None or sample_fmt in allowed_values ])

  def frame_rate(key: str = "rate", label: str = "frame rate"): return MediaEditorFields.rate("fps", key, label, is_int=False)
  def sample_rate(key: str = "rate", label: str = "sample rate"): return MediaEditorFields.rate("hz", key, label, is_int=True)
  def audio_buffer_size(key: str = "buffer_size", label: str = "audio buffer size"): return EditorFields.integer(key=key, label=label, min_value=1)
