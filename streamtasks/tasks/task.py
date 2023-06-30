from streamtasks.tasks.types import TaskDeployment
from streamtasks.client import Client
from abc import ABC, abstractmethod
import asyncio

class Task(ABC):
  def __init__(self, client: Client):
    self.client = client
    self._task = None
    self._stop_signal = asyncio.Event()
    self.app = asgi_app_not_found

  def can_update(self, deployment: TaskDeployment): return False
  async def update(self, deployment: TaskDeployment): pass
  async def stop(self, timeout: float = None): 
    if self._task is None: raise RuntimeError("Task not started")
    self._stop_signal.set()
    try: await asyncio.wait_for(self._task, timeout=timeout)
    except asyncio.TimeoutError: pass
  async def start(self):
    if self._task is not None: raise RuntimeError("Task already started")
    self._task = asyncio.create_task(self.async_start(self._stop_signal))

  @abstractmethod
  async def async_start(self, stop_signal: asyncio.Event): pass
