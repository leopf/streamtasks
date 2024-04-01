import json
from typing import Any
from streamtasks.system.task import MetadataDict

def static_configurator(label: str, description: str | None = None, inputs: list[MetadataDict] = [],
                        outputs: list[MetadataDict] = [], default_config: dict[str, Any] | None = None):
    metadata = {
        "js:configurator": "std:static",
        "cfg:label": label,
        "cfg:inputs": json.dumps(inputs),
        "cfg:outputs": json.dumps([{k: v for k, v in output.items() if k != "key"} for output in outputs]),
        "cfg:outputkeys": json.dumps([output.get("key", None) for output in outputs]),
    }
    if default_config is not None: metadata["cfg:config"] = json.dumps(default_config)
    if description is not None: metadata["cfg:description"] = description
    return metadata
