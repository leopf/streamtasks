from typing import Optional
from streamtasks.asgi import asgi_app_not_found
from abc import ABC, abstractmethod
from streamtasks.client import Client
import asyncio


class Task(ABC):
  def __init__(self, client: Client):
    self.client = client
    self._task = None
    self.app = asgi_app_not_found

  def get_error(self) -> Optional[BaseException]: return None if self._task is None or not self._task.done() else self._task.exception()
  async def stop(self, timeout: float = None):
    if self._task is None: raise RuntimeError("Task not started")
    self._task.cancel()
  async def start(self):
    if self._task is not None: raise RuntimeError("Task already started")
    self._task = asyncio.create_task(self.start_task())

  @abstractmethod
  async def start_task(self): pass