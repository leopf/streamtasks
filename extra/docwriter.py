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

def make_frontmatter(context: dict[str, str]):
  result: dict[str, str] = { "module": context["module_name"] }
  title = context["doc_text"]
  title = title[title.index("#") + 1:]
  title = title[:title.index("\n")].strip()
  result["title"] = title

  if context["module_name"].startswith("streamtasks.system.tasks.inference"): result.update({ "grand_parent": "Tasks", "parent": "Inference Tasks" })
  elif context["module_name"].startswith("streamtasks.system.tasks.ui"): result.update({ "grand_parent": "Tasks", "parent": "UI Tasks" })
  elif context["module_name"].startswith("streamtasks.system.tasks.media"): result.update({ "grand_parent": "Tasks", "parent": "Media Tasks" })
  else: result.update({ "parent": "Tasks" })

  return result

def write_docs(context: dict[str, str]):
  frontmatter = make_frontmatter(context)
  pathlib.Path(context["out_path"]).parent.mkdir(parents=True, exist_ok=True)
  with open(context["out_path"], "w") as fd: fd.write("---\n" + "\n".join(k + ": " + v for k, v in frontmatter.items()) + "\n---\n" + context["doc_text"])

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
You are an assistant writing documentation for the `Task` component of the
StreamTasks system.

The `Task` is composed of two parts: a `Host` responsible for starting tasks and
registering configuration data, and a `Task` itself that defines inputs, outputs,
and editor fields.

Please provide the details of each task, including its inputs, outputs, and any
relevant metadata.

The outline should be:
- title
- inputs
- outputs
- configuration
- description
  - example uses (optional)
  - notes (optional)
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
  try:
    if context["doc_path"] is not None: continue
    print("Writing docs for:", context["module_name"])
    result = ollama.chat(os.getenv("MODEL"), pre_prompt + get_messages(context), options={ "temperature": 0 })
    context["doc_text"] = result["message"]["content"]
    print("doc_text (:-500)", context["doc_text"][:-500])
    write_docs(context)
  except KeyboardInterrupt: raise
  except BaseException as e: print(e)
