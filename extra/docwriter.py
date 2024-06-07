import importlib
import os
import pathlib
from llama_cpp import ChatCompletionRequestMessage, Llama
from streamtasks.system.helpers import get_all_task_hosts
import streamtasks.system.tasks as tasks

SYSTEM_MESSAGE = """
Your job is to write documentation for a system called streamtasks.
The system is a operating system for tasks, which are basically programs. The tasks work by subscribing and providing (both also referred to as registering) topics.
The data is distributed as message pack serializable data, wrapped in "RawData" objects. Topics can be paused.

You will be writing the documentation for the individual tasks.

Each tasks consists of 2 parts. A host and the task iteself. The task host is responsible for starting tasks.
It also registers all the information needed to configure tasks in a node based frontend (sort of like the blender node editor).

An important part of the task host metadata are the editor fields. The editor fields try to make defining a UI as simple as possible.
Labels for the fields are generated from the configuration key they set by replacing underscores with spaces. Refer to the editor fields by their label.

The inputs and output are defined in the task host. Use the label to refer to them. Tasks using the static configurator only have the inputs and outputs listed there.

The answers you provide will be printed directly in the documentation.
- ONLY output the information you were asked for
- Be precise but short
- Only reference variable names when necessary
- The code may have documentation strings. Always include this information.
""".strip()

MODULE_NAME_MESSAGE = "Here is the name of the python module:\n"
PRE_CODE_MESSAGE = "Here is the code for a task and its task host:\n"
REGEN_PROMT = """
The following is the documentation generated from your answers.
Rewrite the documentation. Remove duplicate information and reorganize it. You may change anything but the headers and the order of the headers.
Only answer with the new documentation in markdown, nothing else.
""".strip()

QUESTIONS = {
  "label": "What is the label of the task? Only write the label!",
  "description": """
Describe what the task generally does and how it works. Do NOT list configuration fields, inputs or outputs individually.
You will get the chance to list them and give short descriptions after the next questions.
""".strip(),
  "inputs": """
List the inputs as found in the TaskHost. Name them by their label.
The input key specifies in what config field the topic, which the input is connected to, is saved. So key in_topic means it is saved in the config field in_topic.
Give short descriptions of what the input is for. If you can not identify any inputs, write "None".
""".strip(),
  "outputs": """
List the outputs as found in the TaskHost. Name them by their label.
The outputs key specifies in what config field the topic of the output is saved. So key out_topic means it is saved in the config field out_topic.
Give short descriptions of what the output is for. If you can not identify any outputs, write "None".
""".strip(),
  "config": """
List the configuration fields as found in the TaskHost. Refer to them by their label ("default_value" becomes "default value" etc.).
The key specifies what config field the value is saved to.
""".strip(),
  "description2": """
This is the last information you will be able to give to the reader. Express everything the reader must know, which has not been said yet in the previous answers.
""".strip()
}

def to_markdown(output: dict[str, str]):
  return f"""
# {output['label']}

## Inputs
{output.pop('inputs')}

## Outputs
{output.pop('outputs')}

## Configuration
{output.pop('config')}

## Description
{output.pop('description')}

{output.pop('description2')}
  """.strip()

model = Llama(model_path=os.getenv("MODEL_PATH"), n_gpu_layers=20, n_ctx=5048, verbose=True)
tasks_dir = os.path.dirname(tasks.__file__)

for task_host in get_all_task_hosts():
  module_name = task_host.__module__
  module_path = importlib.import_module(module_name).__file__
  module_sub_path = os.path.relpath(module_path, tasks_dir)
  if os.path.exists(os.path.join("docs/tasks", module_sub_path)): continue

  messages: list[ChatCompletionRequestMessage] = [
    { "role": "system", "content": SYSTEM_MESSAGE },
    { "role": "user", "content": MODULE_NAME_MESSAGE + module_name }
  ]

  with open(module_path, "rt") as fd: messages.append({ "role": "user", "content": PRE_CODE_MESSAGE + fd.read() })
  output = { "module": module_name }
  for k, prompt in QUESTIONS.items():
    print("Working on field", k, "for module", module_name)
    messages.append({ "role": "user", "content": prompt })
    output[k] = model.create_chat_completion(messages, temperature=0)["choices"][0]["message"]["content"]

  md_text = to_markdown(output)
  messages.append({ "role": "user", "content": REGEN_PROMT })
  messages.append({ "role": "user", "content": md_text })
  md_text = model.create_chat_completion(messages, temperature=0)["choices"][0]["message"]["content"]

  out_filename = os.path.join("docs/autogen/tasks", module_sub_path[:-2] + "md")
  pathlib.Path(out_filename).parent.mkdir(parents=True, exist_ok=True)
  text = f"---\n{'\n'.join(k + ': ' + v for k, v in output.items())}\n---\n{md_text}"
  with open(out_filename, "w") as fd: fd.write(text)
