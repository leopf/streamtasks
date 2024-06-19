import logging
import pkgutil
from streamtasks.system.task import TaskHost
import streamtasks.system.tasks as tasks
import importlib

def get_all_task_hosts():
  task_hosts: list[type[TaskHost]] = []
  for module in pkgutil.walk_packages(tasks.__path__, tasks.__name__ + '.'):
    task_host_name_lc = module.name.split(".")[-1].lower() + "taskhost"
    try:
      module = importlib.import_module(module.name)
      task_host_name = next(name for name in module.__dict__.keys() if name.lower() == task_host_name_lc)
      task_host = getattr(module, task_host_name)
      if issubclass(task_host, TaskHost): task_hosts.append(task_host)
    except ImportError as e: logging.debug(f"failed to import module {module.name}. Error: {e}")
    except StopIteration: pass
  return task_hosts
