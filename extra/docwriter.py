import importlib
import os
import pathlib
from streamtasks.system.helpers import get_all_task_hosts
import streamtasks.system.tasks as tasks
import ollama

def remove_frontmatter(md_string: str):
  lines = md_string.splitlines()
  if not lines[0].startswith("---"): return md_string
  end_index = next((i for i, line in enumerate(lines) if line.startswith("---") and i != 0), None)
  if end_index is None: return md_string
  return '\n'.join(lines[end_index + 1:])

def get_messages(context: dict[str, str]) -> list[ollama.Message]:
  return [
    {
      "role": "user",
      "content": f"Write documentation for the task {context['module_name']}. Write a short description, describe the inputs and outputs as well as anything else important to know for the user. Try to not describe the code but focus on the interface and the internal function. Keep it short! Here is the code:\n" + context["code"]
    }
  ]

tasks_dir = os.path.dirname(tasks.__file__)

contexts: list[dict[str, str]] = []

for task_host in get_all_task_hosts():
  module_name = task_host.__module__
  module_path = importlib.import_module(module_name).__file__
  module_sub_path = os.path.relpath(module_path, tasks_dir)
  docs_sub_path = module_sub_path[:-2] + "md"
  docs_path = os.path.join("docs/tasks", docs_sub_path)
  out_path = os.path.join("docs/autogen/tasks", docs_sub_path)
  with open(module_path, "r") as fd: code = fd.read()

  contexts.append({
    "code": code,
    "module_name": module_name,
    "module_path": module_path,
    "out_path": out_path,
    "doc_path": docs_path if os.path.exists(docs_path) else None,
    "rewrite": os.path.exists(out_path)
  })

contexts = sorted(contexts, key=lambda c: c["rewrite"])

pre_prompt: list[ollama.Message] = [
  {
    "role": "system",
    "content": """
Your are an assistant writing documentation for a system called streamtasks.
The system is a operating system for tasks. The tasks work by subscribing and providing (both also referred to as registering) topics.
The data is distributed as message pack serializable data, wrapped in "RawData" objects. Topics can be paused.

You will be writing the documentation for the individual tasks.

Each tasks consists of 2 parts. A host and the task iteself. The task host is responsible for starting tasks.
It also registers all the information needed to configure tasks in a node based frontend.

An important part of the task host metadata are the editor fields. The editor fields try to make defining a UI as simple as possible.
Labels for the fields are generated from the configuration key they set by replacing underscores with spaces. Refer to the editor fields by their label.

The inputs and output are defined in the task host. Use the label to refer to them. Tasks using the static configurator only have the inputs and outputs listed there.

The answers you provide will be printed directly in the documentation.
- ONLY output the information you were asked for
- Be precise but short
- Only reference variable names when necessary
- The code may have documentation strings. Always include this information.
    """.strip()
  }
]

for context in contexts:
  if context["doc_path"] is None: continue
  with open(context["doc_path"]) as fd: doc_text = remove_frontmatter(fd.read())
  pre_prompt.extend(get_messages(context))
  pre_prompt.append({
    "role": "assistant",
    "content": doc_text
  })

for context in contexts:
  if context["doc_path"] is not None: continue
  print("Writing docs for:", context["module_name"])
  result = ollama.chat(os.getenv("MODEL"), pre_prompt + get_messages(context))
  doc_text = result["message"]["content"]
  print("doc_text (:-500)", doc_text[:-500])
  pathlib.Path(context["out_path"]).parent.mkdir(parents=True, exist_ok=True)
  with open(context["out_path"], "w") as fd: fd.write("---\n" + "\n".join(k + ": " + v for k, v in context.items() if isinstance(v, str) and "\n" not in v) + "\n---\n" + doc_text)
