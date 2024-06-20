from itertools import zip_longest
import json
from typing import Any, Literal, NotRequired
from typing_extensions import TypedDict
from streamtasks.system.task import MetadataDict
from streamtasks.utils import strip_nones_from_dict

class IOTypes:
  Type = Literal["ts", "id"]
  Contents = Literal["image", "video", "audio"] | str
  CoderName = str
  CodecName = Literal["raw"] | str
  Width = int
  Height = int
  FrameRate = int | float
  SampleRate = int
  PixelFormat = str
  SampleFormat = str
  Channels = int

class TrackConfig(TypedDict):
  key: str
  label: NotRequired[str]
  multiLabel: NotRequired[str]
  globalIOMap: NotRequired[dict[str, str]]
  defaultConfig: dict[str, Any]
  defaultIO: MetadataDict
  ioMap: dict[str, str]
  editorFields: list[dict]

def static_configurator(label: str, description: str | None = None, inputs: list[MetadataDict] = [],
                        outputs: list[MetadataDict] = [], default_config: dict[str, Any] | None = None,
                        editor_fields: list[dict] | None = None, config_to_output_map: list[dict[str, str] | None] = None,
                        config_to_input_map: dict[str, dict[str, str]] | None = None,
                        io_mirror: list[tuple[str, int]] | None = None, free_inputs: list[str] | None = None):
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
    "cfg:label": label_to_camel_case(label),
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
  if free_inputs is not None: metadata["cfg:freeinputs"] = json.dumps(free_inputs)
  return metadata

def _fix_multitrack_io_config(tc: TrackConfig):
  tc = dict(tc)
  if "ioMap" not in tc: tc["ioMap"] = {}
  if "defaultIO" not in tc: tc["defaultIO"] = {}
  if "defaultConfig" not in tc: tc["defaultConfig"] = {}
  if "editorFields" not in tc: tc["editorFields"] = []
  tc["defaultIO"] = {
    **{ io_key: "" for io_key in tc.get("globalIOMap", {}).values() },
    **tc["defaultIO"],
    **{ io_key: tc["defaultConfig"][config_key] for config_key, io_key in tc["ioMap"].items() }
  }

  return tc

def multitrackio_configurator(track_configs: list[TrackConfig], is_input: bool):
  metadata = {
    "js:configurator": "std:multitrackio",
    "cfg:trackconfigs": json.dumps(list(_fix_multitrack_io_config(tc) for tc in track_configs)),
    "cfg:isinput": "true" if is_input else "false"
  }
  return metadata

def key_to_label(key: str): return key.replace("_", " ")
def label_to_camel_case(label: str): return " ".join(p.capitalize() for p in label.split(" "))

DEFAULT_COLORS = [
    ("#6528f7","akihabara arcade"),
    ("#a076f9","purple illusionist"),
    ("#ffe300","star"),
    ("#ff7800","lucky orange"),
    ("#0cca98","caribbean green"),
    ("#00ffcc","plunge pool"),
    ("#f9a828","carona"),
    ("#eeb76b","olden amber"),
    ("#ade498","sage sensation"),
    ("#ede682","crab-apple"),
    ("#91ca62","bright lettuce"),
    ("#f1ebbb","sandy shore"),
    ("#f8b500","waxy corn"),
    ("#aa14f0","zǐ lúo lán sè violet"),
    ("#bc8cf2","lilac geode"),
    ("#6d67e4","if i could fly"),
    ("#ffc5a1","tomorrow’s coral"),
    ("#ef3f61","eugenia red"),
    ("#df8931","kanafeh"),
    ("#85ef47","lush greenery"),
    ("#f9fd50","biohazard suit"),
]

class EditorFields:
  @staticmethod
  def select(key: str, items: list[tuple[bool | str | float | int, str]], label: str | None = None):
    return strip_nones_from_dict({ "type": "select", "key": key, "label": label or key_to_label(key), "items": [ { "value": value, "label": label } for value, label in items ] })

  @staticmethod
  def multiselect(items: list[dict[str, str | int | float]]): return { "type": "multiselect", "items": items }

  @staticmethod
  def text(key: str, label: str | None = None, multiline: bool | None = None):
    return strip_nones_from_dict({ "type": "text", "key": key, "label": label or key_to_label(key), "multiline": multiline })

  @staticmethod
  def multiline_text(key: str, label: str | None = None): return EditorFields.text(key=key, label=label, multiline=True)

  @staticmethod
  def number(key: str, label: str | None = None, min_value: float | int | None = None, max_value: float | int | None = None, unit: str | None = None, is_int: bool | None = None):
    return strip_nones_from_dict({ "type": "number", "key": key, "label": label or key_to_label(key), "min": min_value, "max": max_value, "unit": unit, "integer": is_int == True })

  @staticmethod
  def integer(key: str, label: str | None = None, min_value: int | None = None, max_value: int | None = None, unit: str | None = None):
    return EditorFields.number(key=key, label=label, min_value=min_value, max_value=max_value, unit=unit, is_int=True)

  @staticmethod
  def slider(key: str, min_value: float | int, max_value: float | int, label: str | None = None, pow: float = 1):
    return strip_nones_from_dict({ "type": "slider", "key": key, "label": label or key_to_label(key), "min": min_value, "max": max_value, "pow": pow })

  @staticmethod
  def boolean(key: str, label: str | None = None):
    return strip_nones_from_dict({ "type": "boolean", "key": key, "label": label or key_to_label(key) })

  @staticmethod
  def options(key: str, label: str | None = None):
    return strip_nones_from_dict({ "type": "kvoptions", "key": key, "label": label or key_to_label(key) })

  @staticmethod
  def repeat_interval(key: str="repeat_interval", label: str | None = None, min_value=0.001):
    return EditorFields.number(key=key, label=label, min_value=min_value, unit="s")

  @staticmethod
  def color_select(key: str, label: str | None = None):
    return EditorFields.select(key=key, label=label, items=DEFAULT_COLORS)
