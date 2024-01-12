from abc import ABC, abstractmethod
import asyncio
from typing import Optional

from pydantic import BaseModel
from streamtasks.asgi import ASGIApp, ASGIAppRunner
from streamtasks.client import Client
from streamtasks.net import Link, Switch
from streamtasks.system.task import Task
from streamtasks.worker import Worker


class TaskTemplate:
  pass


class TaskRunnerRegistration(BaseModel):
  address: int


class TaskRunner(Worker, ABC):
  def __init__(self, node_link: Link, switch: Switch | None = None):
    super().__init__(node_link, switch)
    self.asgi_app: Optional[ASGIApp] = None
    self.client: Client

  async def start(self):
    try:
      self.client = await self.create_client()
      await self.client.request_address()
      registration = TaskRunnerRegistration(
        address=self.client.address,
      )
      webserver = await self.create_webserver()
      webserver_runner = ASGIAppRunner(self.client, webserver, registration.address)

      await asyncio.gather(
        webserver_runner.start(),
        super().start(),
      )
    finally: pass

  @abstractmethod
  async def create_webserver(self) -> ASGIApp: pass
  @abstractmethod
  async def create_task(self, config) -> Task: pass
  @abstractmethod
  async def config_from_task_template(template: TaskTemplate, topic_id_map: dict[str, int]): pass
