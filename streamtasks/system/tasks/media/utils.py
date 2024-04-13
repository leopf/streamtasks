from typing import Literal
from streamtasks.media.util import list_pixel_formats, list_sample_formats, list_sorted_available_codecs

def _key_to_label(key: str): return " ".join(key.split("_"))

class MediaEditorFields:
  def pixel_format(key: str = "pixel_format", label: str | None = None, allowed_values: set[str] | None = None):
    return {
      "type": "select",
      "key": key,
      "label": label or _key_to_label(key),
      "items": [ { "label": pxl_fmt.upper(), "value": pxl_fmt } for pxl_fmt in list_pixel_formats() if allowed_values is None or pxl_fmt in allowed_values ]
    }
  
  def video_codec_name(mode: Literal["w", "r"], key: str = "codec", label: str | None = None):
    return {
      "type": "select",
      "key": key,
      "label": label or _key_to_label(key),
      "items": [ { "label": codec.name.upper(), "value": codec.name } for codec in list_sorted_available_codecs(mode) if codec.type == "video" ]
    }
    
  def audio_codec_name(mode: Literal["w", "r"], key: str = "codec", label: str | None = None):
    return {
      "type": "select",
      "key": key,
      "label": label or _key_to_label(key),
      "items": [ { "label": codec.name.upper(), "value": codec.name } for codec in list_sorted_available_codecs(mode) if codec.type == "audio" ]
    }
  
  def pixel_size(key: str, label: str | None = None):
    return {
      "type": "number",
      "key": key,
      "label": label or _key_to_label(key),
      "integer": True,
      "min": 0,
      "unit": "px"
    }
    
  def boolean(key: str, label: str | None = None):
    return {
      "type": "boolean",
      "key": key,
      "label": label or _key_to_label(key),
    }
    
    
  def options(key: str, label: str | None = None):
    return {
      "type": "kvoptions",
      "key": key,
      "label": label or _key_to_label(key),
    }
    
  def rate(unit: str, key: str = "rate", label: str | None = None):
    return {
      "type": "number",
      "key": key,
      "label": label or _key_to_label(key),
      "integer": True,
      "min": 0,
      "unit": unit
    }
    
  def channel_count(key: str = "channels", label: str | None = None):
    return {
      "type": "number",
      "key": key,
      "label": label or _key_to_label(key),
      "integer": True,
      "min": 1,
      "max": 16,
    }
    
  def sample_format(key: str = "sample_format", label: str | None = None, allowed_values: set[str] | None = None):
    return {
      "type": "select",
      "key": key,
      "label": label or _key_to_label(key),
      "items": [ { "label": pxl_fmt.upper(), "value": pxl_fmt } for pxl_fmt in list_sample_formats() if allowed_values is None or pxl_fmt in allowed_values ]
    }
    
  def frame_rate(key: str = "rate", label: str = "frame rate"): return MediaEditorFields.rate("fps", key, label)
  def sample_rate(key: str = "rate", label: str = "sample rate"): return MediaEditorFields.rate("hz", key, label)