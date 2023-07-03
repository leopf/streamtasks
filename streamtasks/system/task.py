from streamtasks.system.types import TaskDeployment, TaskDeploymentStatus
from streamtasks.system.helpers import asgi_app_not_found
from abc import ABC, abstractmethod
import asyncio

from streamtasks.client import Client
class Task(ABC):
  def __init__(self, client: Client):
    self.client = client
    self._task = None
    self.app = asgi_app_not_found

  def get_deployment_status(self) -> TaskDeploymentStatus: 
    error = None if self._task is None or not self._task.done() else self._task.exception()
    return TaskDeploymentStatus(
      running=self._task is not None and not self._task.done(),
      error=str(error) if error is not None else None)

  def can_update(self, deployment: TaskDeployment): return False
  async def update(self, deployment: TaskDeployment): pass
  async def stop(self, timeout: float = None): 
    if self._task is None: raise RuntimeError("Task not started")
    self._task.cancel()
  async def start(self):
    if self._task is not None: raise RuntimeError("Task already started")
    self._task = asyncio.create_task(self.start_task())

  @abstractmethod
  async def start_task(self): pass

