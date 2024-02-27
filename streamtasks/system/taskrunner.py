from abc import ABC, abstractmethod
import asyncio
from contextlib import asynccontextmanager
from enum import Enum
from typing import Optional

from pydantic import BaseModel
from streamtasks.asgi import ASGIApp, ASGIAppRunner
from streamtasks.client import Client
from streamtasks.client.discovery import address_name_context
from streamtasks.client.fetch import FetchServer
from streamtasks.net import Link, Switch
from streamtasks.system.task import Task
from streamtasks.worker import Worker


class TaskTemplate:
  pass


class TaskRunnerRegistrationBase(BaseModel):
  id: str


class TaskRunnerRegistration(TaskRunnerRegistrationBase):
  address: int


class TaskBase(BaseModel):
  id: str


class TaskStatus(TaskBase):
  running: bool
  error_message: Optional[str]


class TaskTemplateDeployment(TaskBase):
  topic_id_map: dict[str, int]
  template: TaskTemplate


class TaskConfigDeployment(TaskBase):
  config: dict


class SystemNames(Enum):
  TASK_MANAGER = "taskmanager"


class TaskManager(Worker):
  def __init__(self, node_link: Link, switch: Switch | None = None):
    super().__init__(node_link, switch)
    self.runners: dict[str, TaskRunnerRegistration] = {}
    self.tasks: dict[str, TaskStatus] = {}
    self.client: Client

  async def start(self):
    self.client = await self.create_client()
    self.client.start()

    await self.client.request_address()
    async with address_name_context(self.client, SystemNames.TASK_MANAGER, self.client.address):
      await asyncio.gather(
        self.run_fetch_server(),
        super().start(),
      )

  async def run_fetch_server(self):
    server = FetchServer(self.client)

    @server.route("/runner/register")
    def register_runner(data):
      runner = TaskRunnerRegistration.model_validate(data)
      self.runners[runner.id] = runner

    @server.route("/runner/unregister")
    def unregister_runner(data):
      runner = TaskRunnerRegistrationBase.model_validate(data)
      self.runners.pop(runner.id, None)

    @server.route("/task/status")
    def report_task_status(data):
      status = TaskStatus.model_validate(data)
      self.tasks[status.id] = status


class TaskManagerClient:
  def __init__(self, client: Client) -> None:
    self.client = client

  @asynccontextmanager
  async def registration_context(self, id: str, address: int):
    try:
      await self.client.fetch(SystemNames.TASK_MANAGER, "/runner/register", TaskRunnerRegistration(id=id, address=address).model_dump())
      yield None
    finally:
      await self.client.fetch(SystemNames.TASK_MANAGER, "/runner/unregister", TaskRunnerRegistrationBase(id=id).model_dump())

  async def report_task_status(self, task_id: str, running: bool, error: Optional[str | BaseException]):
    assert error is None or not running, "error must be none if the task is running!"
    await self.client.fetch(SystemNames.TASK_MANAGER, "/task/status", TaskStatus(id=task_id, running=running, error_message=None if error is None else str(error)).model_dump())

  async def start_task_from_template(self, deployment: TaskTemplateDeployment):
    await self.client.fetch(SystemNames.TASK_MANAGER, "/task/start_from_template", deployment.model_dump())

  async def start_task_from_config(self, id: str, config: dict):
    await self.client.fetch(SystemNames.TASK_MANAGER, "/task/start_from_config", TaskConfigDeployment(id=id, config=config).model_dump())

  async def stop_task(self, task_id: str):
    await self.client.fetch(SystemNames.TASK_MANAGER, "/task/stop", TaskBase(id=task_id).model_dump())


class TaskRunner(Worker, ABC):
  def __init__(self, node_link: Link, switch: Switch | None = None):
    super().__init__(node_link, switch)
    self.asgi_app: Optional[ASGIApp] = None
    self.client: Client

  async def start(self):
    try:
      self.client = await self.create_client()
      await self.client.request_address()

      webserver = await self.create_webserver()
      webserver_runner = ASGIAppRunner(self.client, webserver, self.client.address)
      manager_client = TaskManagerClient(self.client)

      async with manager_client.registration_context(id="", address=self.client.address):
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
