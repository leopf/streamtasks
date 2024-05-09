from typing import Literal
from streamtasks.media.util import list_pixel_formats, list_sample_formats, list_sorted_available_codecs
from streamtasks.system.configurators import EditorFields

class MediaEditorFields:
  def pixel_format(key: str = "pixel_format", label: str | None = None, allowed_values: set[str] | None = None):
    return EditorFields.select(key=key, label=label,
      items=[ (pxl_fmt, pxl_fmt.upper()) for pxl_fmt in list_pixel_formats() if allowed_values is None or pxl_fmt in allowed_values])
  
  def codec_name(mode: Literal["w", "r"], codec_type: str, key: str = "codec", label: str | None = None):
    return EditorFields.select(key=key, label=label,
      items=[ (codec.name, codec.name.upper()) for codec in list_sorted_available_codecs(mode) if codec.type == codec_type])
  
  def video_codec_name(mode: Literal["w", "r"], key: str = "codec", label: str | None = None):
    return MediaEditorFields.codec_name(mode=mode, key=key, codec_type="video", label=label)
  
  def audio_codec_name(mode: Literal["w", "r"], key: str = "codec", label: str | None = None):
    return MediaEditorFields.codec_name(mode=mode, key=key, codec_type="audio", label=label)

  def pixel_size(key: str, label: str | None = None):
    return EditorFields.number(key=key, label=label, is_int=True, min_value=0, unit="px")
    
  def rate(unit: str, key: str = "rate", label: str | None = None):
    return EditorFields.number(key=key, label=label, unit=unit, is_int=True, min_value=0)
    
  def channel_count(key: str = "channels", label: str | None = None):
    return EditorFields.number(key=key, label=label, is_int=True, min_value=1, max_value=16)
    
  def sample_format(key: str = "sample_format", label: str | None = None, allowed_values: set[str] | None = None):
    return EditorFields.select(key=key, label=label,
      items=[ (sample_fmt, sample_fmt.upper()) for sample_fmt in list_sample_formats() if allowed_values is None or sample_fmt in allowed_values ])

  def frame_rate(key: str = "rate", label: str = "frame rate"): return MediaEditorFields.rate("fps", key, label)
  def sample_rate(key: str = "rate", label: str = "sample rate"): return MediaEditorFields.rate("hz", key, label)
  def audio_buffer_size(key: str = "buffer_size", label: str = "audio buffer size"): return EditorFields.number(key=key, label=label, min_value=1, is_int=True)
