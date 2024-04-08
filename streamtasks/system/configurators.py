from itertools import zip_longest
import json
from typing import Any
from streamtasks.system.task import MetadataDict

def static_configurator(label: str, description: str | None = None, inputs: list[MetadataDict] = [],
                        outputs: list[MetadataDict] = [], default_config: dict[str, Any] | None = None,
                        editor_fields: list[dict] | None = None, config_to_output_map: list[dict[str, str] | None] = None,
                        config_to_input_map: dict[str, dict[str, str]] | None = None):
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
  if config_to_output_map is not None: metadata["cfg:outputmetadata"] = json.dumps(config_to_output_map)
  if config_to_input_map is not None: metadata["cfg:inputmetadata"] = json.dumps(config_to_input_map)
  return metadata
