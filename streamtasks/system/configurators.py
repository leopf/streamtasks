from itertools import zip_longest
import json
from typing import Any, Literal, NotRequired, TypedDict
from streamtasks.system.task import MetadataDict

class IOTypes:
  Type = Literal["ts", "id"]
  Contents = Literal["image", "video", "audio"] | str
  Codec = Literal["raw"] | str
  Width = int
  Height = int
  Rate = int
  PixelFormat = str
  SampleFormat = str
  Channels = int
  
class TrackConfig(TypedDict):
  key: str
  label: NotRequired[str]
  defaultConfig: dict[str, Any]
  defaultIO: MetadataDict
  ioMap: dict[str, str]
  editorFields: list[dict]

def static_configurator(label: str, description: str | None = None, inputs: list[MetadataDict] = [],
                        outputs: list[MetadataDict] = [], default_config: dict[str, Any] | None = None,
                        editor_fields: list[dict] | None = None, config_to_output_map: list[dict[str, str] | None] = None,
                        config_to_input_map: dict[str, dict[str, str]] | None = None,
                        io_mirror: list[tuple[str, int]] | None = None):
  if default_config is not None:
    if config_to_output_map is not None: 
      for output, cfg_map in zip_longest(outputs, config_to_output_map[:len(outputs)], fillvalue=None):
        output.update({ out_metadata_key: default_config[cfg_key] for cfg_key, out_metadata_key in cfg_map.items() })
    if config_to_input_map:
      for input_key, cfg_map in config_to_input_map.items():
        if (tinput := next((i for i in inputs if i["key"] == input_key), None)) is not None:
          tinput.update({ in_metadata_key: default_config[cfg_key] for cfg_key, in_metadata_key in cfg_map.items() })
      
  metadata = {
    "js:configurator": "std:static",
    "cfg:label": label,
    "cfg:inputs": json.dumps(inputs),
    "cfg:outputs": json.dumps([{k: v for k, v in output.items() if k != "key"} for output in outputs]),
    "cfg:outputkeys": json.dumps([output.get("key", None) for output in outputs]),
  }
  if default_config is not None: metadata["cfg:config"] = json.dumps(default_config)
  if description is not None: metadata["cfg:description"] = description
  if editor_fields is not None: metadata["cfg:editorfields"] = json.dumps(editor_fields)
  if config_to_input_map is not None: metadata["cfg:config2inputmap"] = json.dumps(config_to_input_map)
  if config_to_output_map is not None: metadata["cfg:config2outputmap"] = json.dumps(config_to_output_map)
  if io_mirror is not None: metadata["cfg:iomirror"] = json.dumps(io_mirror)
  return metadata

def multitrackio_configurator(track_configs: list[TrackConfig], is_input: bool):
  metadata = {
    "js:configurator": "std:multitrackio",
    "cfg:trackconfigs": json.dumps(track_configs),
    "cfg:isinput": "true" if is_input else "false"
  }
  return metadata

def _key_to_label(key: str): return " ".join(key.split("_"))
def _strip_nones(data: dict): return { k: v for k, v in data.items() if v is not None }

class EditorFields:
  def select(key: str, items: list[tuple[bool | str | float | int, str]], label: str | None = None):
    return _strip_nones({ "type": "select", "key": key, "label": label or _key_to_label(key), "items": [ { "value": value, "label": label } for value, label in items ] })
  
  def text(key: str, label: str | None = None):
    return _strip_nones({ "type": "text", "key": key, "label": label or _key_to_label(key) })
  
  def number(key: str, label: str | None = None, min_value: float | int | None = None, max_value: float | int | None = None, unit: str | None = None, is_int: bool | None = None):
    return _strip_nones({ "type": "number", "key": key, "label": label or _key_to_label(key), "min": min_value, "max": max_value, "unit": unit, "integer": is_int == True })

  def boolean(key: str, label: str | None = None):
    return _strip_nones({ "type": "boolean", "key": key, "label": label or _key_to_label(key) })
  
  def options(key: str, label: str | None = None):
    return _strip_nones({ "type": "kvoptions", "key": key, "label": label or _key_to_label(key) })