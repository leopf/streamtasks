import logging
from streamtasks.system.task import TaskHost
import streamtasks.system.tasks as tasks
import os
import glob
import importlib

def get_all_task_hosts():
  tasks_dir = os.path.dirname(tasks.__file__)
  task_hosts: list[type[TaskHost]] = []
  for module_path in glob.glob("**/**.py", root_dir=tasks_dir, recursive=True):
    module_sub_name = module_path[:-3].replace("/", ".").replace("\\", ".")
    task_host_name_lc = module_sub_name.split(".")[-1] + "taskhost"
    try:
      module = importlib.import_module("streamtasks.system.tasks." + module_sub_name)
      task_host_name = next(name for name in module.__dict__.keys() if name.lower() == task_host_name_lc)
      task_host = getattr(module, task_host_name)
      if issubclass(task_host, TaskHost): task_hosts.append(task_host)
    except ImportError as e: logging.debug(f"failed to import module {"streamtasks.system.tasks." + module_sub_name}. Error: {e}")
    except StopIteration: pass
  return task_hosts
