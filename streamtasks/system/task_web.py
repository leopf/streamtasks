from abc import abstractmethod
import asyncio
import itertools
import json
import logging
import mimetypes
import os
import re
import shelve
from typing import Any, Literal
from typing_extensions import TypedDict
from uuid import UUID, uuid4
from pydantic import UUID4, BaseModel, Field, TypeAdapter, ValidationError, field_serializer, field_validator
from streamtasks.asgi import ASGIAppRunner, ASGIProxyApp
from streamtasks.asgiserver import ASGIHandler, ASGIRouter, ASGIServer, HTTPContext, TransportContext, WebsocketContext, decode_data_uri, http_context_handler, path_rewrite_handler, static_content_handler, static_files_handler, transport_context_handler, websocket_context_handler
from streamtasks.client import Client
from streamtasks.client.discovery import delete_topic_space, get_topic_space_translation, register_address_name, register_topic_space, wait_for_address_name
from streamtasks.client.fetch import FetchError, FetchErrorStatusCode, FetchRequest, FetchServer
from streamtasks.client.receiver import TopicsReceiver
from streamtasks.client.signal import SignalServer
from streamtasks.env import get_data_sub_dir
from streamtasks.net import EndpointOrAddress, Link
from streamtasks.net.serialization import RawData
from streamtasks.net.utils import str_to_endpoint
from streamtasks.services.protocols import AddressNames
from streamtasks.system.task import TASK_CONSTANTS, MetadataDict, MetadataFields, ModelWithId, TaskHostRegistration, TaskHostRegistrationList, TaskInstance, TaskManagerClient, TaskNotFoundError
from streamtasks.utils import get_node_name_id, make_json_serializable, wait_with_dependencies
from streamtasks.worker import Worker
import importlib.resources

class DeploymentBase(ModelWithId):
  id: UUID4 = Field(default_factory=uuid4)
  label: str

class FullDeployment(DeploymentBase):
  status: Literal["scheduled", "running", "offline"] = "offline"

class RunningDeployment(ModelWithId):
  started: bool = False
  topic_space_id: int
  task_instances: dict[UUID4, TaskInstance]
  task_instance_configs: dict[UUID4, Any] | None

class TaskOutput(TypedDict):
  topic_id: int

class StoredTask(ModelWithId):
  deployment_id: UUID4
  task_host_id: str
  label: str
  config: dict[str, Any]
  frontend_config: dict[str, Any]
  inputs: list[MetadataDict]
  outputs: list[MetadataDict]

class FullTask(StoredTask):
  task_instance: TaskInstance | None = None

class UpdateTaskInstanceMessage(ModelWithId):
  task_instance: TaskInstance

class DeploymentDashboardWindow(BaseModel):
  task_id: UUID4
  x: float
  y: float
  width: float
  height: float

class DeploymentDashboard(ModelWithId):
  deployment_id: UUID4
  label: str
  windows: list[DeploymentDashboardWindow]

  @field_serializer("deployment_id")
  def serialize_deployment_id(self, id: UUID4): return str(id)

class PathRegistrationFrontend(BaseModel):
  path: str
  label: str

  @field_validator("path")
  @classmethod
  def validate_path(cls, value: str):
    if value.startswith("std:"): return value # allow for std frontends
    if value.startswith("/"): raise ValueError("path must not start with /")
    if value != os.path.normpath(value): raise ValueError("path must be normalized!")
    if not re.match(r'^[a-zA-Z0-9\-_./]*$', value): raise ValueError("Invalid path!")
    return value

class PathRegistration(BaseModel):
  id: str
  path: str
  endpoint: EndpointOrAddress
  frontend: PathRegistrationFrontend | None = None

  @field_validator("path")
  @classmethod
  def validate_path(cls, value: str):
    if not value.endswith("/"): raise ValueError("path must end with /")
    if not value.startswith("/"): raise ValueError("path must start with /")
    if not re.match(r'^[a-zA-Z0-9\-_/]*$', value): raise ValueError("Invalid path!")
    return value

FullDeploymentList = TypeAdapter(list[FullDeployment])
FullTaskList = TypeAdapter(list[FullTask])
DeploymentDashboardList = TypeAdapter(list[DeploymentDashboard])

class TaskWebPathHandler(Worker):
  def __init__(self, link: Link, path: str, frontend: PathRegistrationFrontend | None = None, register_endpoits: list[EndpointOrAddress] = [AddressNames.TASK_MANAGER_WEB]):
    super().__init__(link)
    self.register_endpoits = list(register_endpoits)
    self.path = path
    self.frontend = frontend
    self.id = get_node_name_id("TaskWebPathHandler" + self.__class__.__name__)
    self.client: Client

  async def run(self):
    try:
      await self.setup()
      self.client = await self.create_client()
      self.client.start()
      await self.client.request_address()
      for reg_ep in self.register_endpoits:
        address = reg_ep[0] if isinstance(reg_ep, tuple) else reg_ep
        if isinstance(address, str): await wait_for_address_name(self.client, address)
        await self.client.fetch(reg_ep, TASK_CONSTANTS.FD_TMW_REGISTER_PATH, PathRegistration(id=self.id, endpoint=self.client.address, frontend=self.frontend, path=self.path).model_dump())
      await self.run_inner()
    finally: await self.shutdown()

  @abstractmethod
  async def run_inner(self): pass

class TaskWebBackendStore:
  def __init__(self) -> None:
    self.running_deployments: dict[UUID4, RunningDeployment] = {}

    data_dir = get_data_sub_dir("user-data")
    self.deployments: shelve.Shelf = shelve.open(os.path.join(data_dir, "deployments.db"))
    self.tasks: shelve.Shelf = shelve.open(os.path.join(data_dir, "tasks.db"))
    self.dashboards: shelve.Shelf = shelve.open(os.path.join(data_dir, "dashboards.db"))

  def __del__(self):
    self.deployments.close()
    self.dashboards.close()
    self.tasks.close()

  def set_running_deployment(self, deployment: RunningDeployment): self.running_deployments[deployment.id] = deployment
  def get_running_deployment(self, deployment_id: UUID4): return self.running_deployments[deployment_id]
  def delete_running_deployment(self, deployment_id: UUID4): return self.running_deployments.pop(deployment_id)

  async def all_dashboards(self) -> list[DeploymentDashboard]: return [DeploymentDashboard.model_validate_json(v) for v in self.dashboards.values()]
  async def all_dashboards_in_deployment(self, deployment_id: UUID4) -> list[DeploymentDashboard]: return [ db for db in await self.all_dashboards() if db.deployment_id == deployment_id ]
  async def get_dashboard(self, id: UUID4) -> DeploymentDashboard:  return DeploymentDashboard.model_validate_json(self.dashboards[str(id)])
  async def create_or_update_dashboard(self, db: DeploymentDashboard) -> DeploymentDashboard: self.dashboards[str(db.id)] = db.model_dump_json()
  async def delete_dashboard(self, id: UUID4): return self.dashboards.pop(str(id), None)

  async def all_deployments(self) -> list[DeploymentBase]: return [ self.deployment_apply_running(FullDeployment.model_validate_json(d)) for d in self.deployments.values() ]
  async def get_deployment(self, id: UUID4) -> DeploymentBase: return self.deployment_apply_running(FullDeployment.model_validate_json(self.deployments[str(id)]))
  async def create_deployment(self, deployment: DeploymentBase) -> DeploymentBase:
    if str(deployment.id) in self.deployments: raise ValueError("Deployment already exists!")
    self.deployments[str(deployment.id)] = deployment.model_dump_json()
  async def update_deployment(self, deployment: DeploymentBase) -> DeploymentBase:
    if deployment.id in self.running_deployments: raise ValueError("Deployment is running!")
    if str(deployment.id) not in self.deployments: raise ValueError("Deployment does not exists!")
    self.deployments[str(deployment.id)] = deployment.model_dump_json()
  async def delete_deployment(self, id: UUID4):
    if id in self.running_deployments: raise ValueError("Deployment is running!")
    res = self.deployments.pop(str(id), None)
    if res is None: raise ValueError("Deployment does not exist!")

  async def all_tasks(self) -> list[FullTask]: return [self.task_apply_instance(FullTask.model_validate_json(v)) for v in self.tasks.values()]
  async def all_tasks_in_deployment(self, deployment_id: UUID4) -> list[FullTask]: return [ task for task in await self.all_tasks() if task.deployment_id == deployment_id ]
  async def get_task(self, id: UUID4) -> FullTask:  return self.task_apply_instance(FullTask.model_validate_json(self.tasks[str(id)]))
  async def create_or_update_task(self, task: StoredTask) -> StoredTask:
    if task.deployment_id in self.running_deployments: raise ValueError("Deployment is running!")
    if str(task.id) in self.tasks:
      existing_task = await self.get_task(task.id)
      if existing_task.deployment_id in self.running_deployments: raise ValueError("Deployment is running!")
    self.tasks[str(task.id)] = task.model_dump_json()
  async def delete_task(self, id: UUID4):
    task = await self.get_task(id)
    if task.deployment_id in self.running_deployments: raise ValueError("Deployment is running!")
    self.tasks.pop(str(id), None)

  def deployment_apply_running(self, deployment: FullDeployment):
    if (running_deployment := self.running_deployments.get(deployment.id, None)) is not None: deployment.status = "running" if running_deployment.started else "scheduled"
    return deployment
  def task_apply_instance(self, task: FullTask):
    if task.deployment_id in self.running_deployments: task.task_instance = self.running_deployments[task.deployment_id].task_instances.get(task.id, None)
    return task

class TaskWebBackend(Worker):
  def __init__(self, link: Link, address_name: str = AddressNames.TASK_MANAGER_WEB,
               task_manager_address_name: str = AddressNames.TASK_MANAGER):
    super().__init__(link)
    self.task_manager_address_name = task_manager_address_name
    self.address_name = address_name
    self.task_host_asgi_handlers: dict[str, ASGIHandler] = {}
    self.task_asgi_handlers: dict[UUID4, ASGIHandler] = {}
    self.deployment_task_listeners: dict[UUID4, asyncio.Task] = {}
    self.path_registrations: list[PathRegistration] = []
    self.store = TaskWebBackendStore()
    self.client: Client
    self.tm_client: TaskManagerClient

  async def run(self):
    try:
      await self.setup()
      self.client = await self.create_client()
      self.client.start()
      await self.client.request_address()
      await register_address_name(self.client, self.address_name)
      self.tm_client = TaskManagerClient(self.client, self.task_manager_address_name)
      await asyncio.gather(self.run_asgi_server(), self.run_fetch_api(), self.run_signal_api())
    finally:
      await self.shutdown()

  async def run_fetch_api(self):
    server = FetchServer(self.client)

    @server.route(TASK_CONSTANTS.FD_TMW_REGISTER_PATH)
    async def _(req: FetchRequest):
      body = PathRegistration.model_validate(req.body)
      self.path_registrations.append(body)
      await req.respond(None)

    await server.run()

  async def run_signal_api(self):
    server = SignalServer(self.client)

    @server.route(TASK_CONSTANTS.SD_TMW_UNREGISTER_PATH)
    async def _(message_data: Any):
      data = ModelWithId.model_validate(message_data)
      self.path_registrations = [ reg for reg in self.path_registrations if reg.id != data.id]

    await server.run()

  async def run_asgi_server(self):
    app = ASGIServer()

    @app.handler
    @http_context_handler
    async def _error_handler(ctx: HTTPContext):
      try:
        await ctx.next()
      except (ValidationError, ValueError) as e:
        await ctx.respond_text(str(e), 400)
      except KeyError as e: await ctx.respond_text(str(e), 404)
      except FetchError as e:
        if e.status_code == FetchErrorStatusCode.NOT_FOUND: await ctx.respond_text(str(e), 404)
        if e.status_code == FetchErrorStatusCode.BAD_REQUEST: await ctx.respond_text(str(e), 400)
        if e.status_code == FetchErrorStatusCode.GENERAL: await ctx.respond_text(str(e), 500)
      except BaseException as e:
        await ctx.respond_text(str(e), 500)

    router = ASGIRouter()
    app.add_handler(router)

    @router.get("/api/task-hosts")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json_raw(TaskHostRegistrationList.dump_json(await self.tm_client.list_task_hosts()))

    @router.get("/api/task-host/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json_string((await self.tm_client.get_task_host(ctx.params.get("id", None))).model_dump_json())

    @router.get("/api/deployments")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json_raw(FullDeploymentList.dump_json(await self.store.all_deployments()))

    @router.post("/api/deployment/{id}/schedule")
    @http_context_handler
    async def _(ctx: HTTPContext):
      deployment_id = UUID(ctx.params.get("id", ""))
      tasks = await self.store.all_tasks_in_deployment(deployment_id)
      topic_ids = set(itertools.chain.from_iterable((int(output["topic_id"]) for output in task.outputs) for task in tasks))
      topic_space_id, _ = await register_topic_space(self.client, topic_ids)
      running_deployment = RunningDeployment(id=deployment_id, topic_space_id=topic_space_id, task_instances={}, task_instance_configs={})
      self.store.set_running_deployment(running_deployment)
      for task in tasks:
        task_instance = await self.tm_client.schedule_task(task.task_host_id, topic_space_id)
        running_deployment.task_instances[task.id] = task_instance
        running_deployment.task_instance_configs[task_instance.id] = task.config
      self.deployment_task_listeners[deployment_id] = asyncio.create_task(self.run_deployment_task_listener(running_deployment))
      await ctx.respond_json_string((await self.store.get_deployment(deployment_id)).model_dump_json())

    @router.post("/api/deployment/{id}/start")
    @http_context_handler
    async def _(ctx: HTTPContext):
      deployment_id = UUID(ctx.params.get("id", ""))
      running_deployment = self.store.get_running_deployment(deployment_id)
      for (task_id, task_instance) in running_deployment.task_instances.items():
        new_task_instance = await self.tm_client.start_task(task_instance.id, running_deployment.task_instance_configs.get(task_instance.id, None))
        running_deployment.task_instances[task_id] = new_task_instance
      running_deployment.task_instance_configs = None
      await ctx.respond_json_string((await self.store.get_deployment(deployment_id)).model_dump_json())

    @router.post("/api/deployment/{id}/stop")
    @http_context_handler
    async def _(ctx: HTTPContext):
      deployment_id = UUID(ctx.params.get("id", ""))
      running_deployment = self.store.get_running_deployment(deployment_id)

      for task_instance in running_deployment.task_instances.values():
        try: await self.tm_client.cancel_task_wait(task_instance.id)
        except TaskNotFoundError: pass
      await delete_topic_space(self.client, running_deployment.topic_space_id)

      if (listener_task := self.deployment_task_listeners.pop(deployment_id, None)) is not None: listener_task.cancel()
      self.store.delete_running_deployment(deployment_id)

      await ctx.respond_json_string((await self.store.get_deployment(deployment_id)).model_dump_json())

    @router.get("/api/deployment/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json_string((await self.store.get_deployment(UUID(ctx.params.get("id", "")))).model_dump_json())

    @router.post("/api/deployment")
    @http_context_handler
    async def _(ctx: HTTPContext):
      deployment = DeploymentBase.model_validate_json(await ctx.receive_json_raw())
      await self.store.create_deployment(deployment)
      await ctx.respond_json_string(deployment.model_dump_json())

    @router.put("/api/deployment")
    @http_context_handler
    async def _(ctx: HTTPContext):
      deployment = DeploymentBase.model_validate_json(await ctx.receive_json_raw())
      await self.store.update_deployment(deployment)
      await ctx.respond_json_string(deployment.model_dump_json())

    @router.delete("/api/deployment/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      await self.store.delete_deployment(UUID(ctx.params.get("id", "")))
      await ctx.respond_status(200)

    @router.get("/api/deployment/{id}/dashboards")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json_raw(DeploymentDashboardList.dump_json(await self.store.all_dashboards_in_deployment(UUID(ctx.params.get("id", "")))))

    @router.get("/api/dashboard/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      db = await self.store.get_dashboard(UUID(ctx.params.get("id", "")))
      await ctx.respond_json_string(db.model_dump_json())

    @router.delete("/api/dashboard/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      await self.store.delete_dashboard(UUID(ctx.params.get("id", "")))
      await ctx.respond_status(200)

    @router.put("/api/dashboard")
    @http_context_handler
    async def _(ctx: HTTPContext):
      db = DeploymentDashboard.model_validate_json(await ctx.receive_json_raw())
      await self.store.create_or_update_dashboard(db)
      await ctx.respond_json_string(db.model_dump_json())

    @router.get("/api/deployment/{id}/tasks")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json_raw(FullTaskList.dump_json(await self.store.all_tasks_in_deployment(UUID(ctx.params.get("id", "")))))

    @router.delete("/api/task/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      await self.store.delete_task(UUID(ctx.params.get("id", "")))
      await ctx.respond_status(200)

    @router.put("/api/task")
    @http_context_handler
    async def _(ctx: HTTPContext):
      task = StoredTask.model_validate_json(await ctx.receive_json_raw())
      await self.store.create_or_update_task(task)
      await ctx.respond_json_string(task.model_dump_json())

    async def ws_topic_handler(ctx: WebsocketContext, topic_id: int):
      try:
        await ctx.accept()
        receive_disconnect_task = asyncio.create_task(ctx.receive_disconnect())
        async with TopicsReceiver(self.client, [ topic_id ]) as recv:
          while ctx.connected:
            _, data = await wait_with_dependencies(recv.get(), [receive_disconnect_task])
            try:
              if isinstance(data, RawData): await ctx.send_message(f'{{ "data": {json.dumps(make_json_serializable(data.data), allow_nan=False)} }}')
            except BaseException as e: logging.warning("Failed to send message ", e)
      except asyncio.CancelledError: pass
      finally:
        receive_disconnect_task.cancel()
        await ctx.close()

    @router.get("/api/path-registrations")
    @http_context_handler
    async def _(ctx: HTTPContext):
      await ctx.respond_json([ { "id": reg.id, "path": reg.path, "frontend": None if reg.frontend is None else { "label": reg.frontend.label, "path": reg.frontend.path } } for reg in self.path_registrations ])

    @router.websocket_route("/deployment/{deployment_id}/task-instances")
    @websocket_context_handler
    async def _(ctx: WebsocketContext):
      try:
        await ctx.accept()
        receive_disconnect_task = asyncio.create_task(ctx.receive_disconnect())
        deployment = self.store.get_running_deployment(UUID(ctx.params.get("deployment_id", "")))
        update_generator = self.receive_deployment_task_instance_updates(deployment)
        while ctx.connected:
          task_id, task_instance = await wait_with_dependencies(anext(update_generator), [receive_disconnect_task])
          await ctx.send_message(UpdateTaskInstanceMessage(id=task_id, task_instance=task_instance).model_dump_json())
      finally:
        receive_disconnect_task.cancel()
        await ctx.close()

    @router.websocket_route("/topic/{topic_id}")
    @websocket_context_handler
    async def _(ctx: WebsocketContext):
      topic_id = int(ctx.params.get("topic_id"))
      await ws_topic_handler(ctx, topic_id)

    @router.websocket_route("/topic/{topic_space_id}/{topic_id}")
    @websocket_context_handler
    async def _(ctx: WebsocketContext):
      topic_id = int(ctx.params.get("topic_id"))
      topic_space_id = int(ctx.params.get("topic_space_id"))
      actual_topic_id = await get_topic_space_translation(self.client, topic_space_id, topic_id)
      await ws_topic_handler(ctx, actual_topic_id)

    # TODO: lifecycle api support
    @router.transport_route("/task/{id}/{path*}")
    @path_rewrite_handler("/{path*}")
    @transport_context_handler
    async def _(ctx: TransportContext):
      id: UUID4 = UUID(ctx.params.get("id", ""))
      await ctx.delegate(await self.get_task_asgi_handler(id))

    # TODO: lifecycle api support
    @router.transport_route("/task-host/{id}/{path*}")
    @path_rewrite_handler("/{path*}")
    @transport_context_handler
    async def _(ctx: TransportContext):
      id = ctx.params.get("id", "")
      await ctx.delegate(await self.get_task_host_asgi_handler(id))

    @router.handler
    @transport_context_handler
    async def _(ctx: TransportContext):
      for reg in self.path_registrations:
        if ctx.path.startswith(reg.path):
          return await ctx.delegate(ASGIProxyApp(self.client, reg.endpoint), { **ctx.scope, "path": ctx.path[len(reg.path) - 1:] })
      await ctx.next()

    router.add_handler(static_files_handler(importlib.resources.files("streamtasks.system").joinpath("assets/public/"), ["index.html"]))

    await ASGIAppRunner(self.client, app).run()

  async def run_deployment_task_listener(self, deployment: RunningDeployment):
    async for task_id, task_instance in self.receive_deployment_task_instance_updates(deployment):
      deployment.task_instances[task_id] = task_instance

  async def receive_deployment_task_instance_updates(self, deployment: RunningDeployment):
    task_instance_ids = [ ti.id for ti in deployment.task_instances.values() ]
    task_instance_id_map = { ti.id: task_id for task_id, ti in deployment.task_instances.items() }
    async with self.tm_client.task_message_receiver(task_instance_ids) as receiver:
      while True:
        task_instance = await receiver.get()
        if (task_id := task_instance_id_map.get(task_instance.id, None)) is not None:
          yield (task_id, task_instance)

  async def get_task_host_asgi_handler(self, id: str) -> ASGIHandler:
    if (router := self.task_host_asgi_handlers.get(id, None)) is None:
      reg: TaskHostRegistration = await self.tm_client.get_task_host(id)
      self.task_host_asgi_handlers[id] = router = self._metadata_to_router(reg.metadata)
    return router

  async def get_task_asgi_handler(self, id: UUID4) -> ASGIHandler:
    if (router := self.task_asgi_handlers.get(id, None)) is None:
      reg: TaskInstance = await self.tm_client.get_task(id)
      self.task_asgi_handlers[id] = router = self._metadata_to_router(reg.metadata)
    return router

  def _metadata_to_router(self, metadata: MetadataDict) -> ASGIHandler:
    router = ASGIRouter()
    for (path, content) in ((k[5:], v) for k, v in metadata.items() if isinstance(v, str) and k.lower().startswith("file:")):
      guessed_mime_type = mimetypes.guess_type(path)[0]
      if content.startswith("data:"):
        # TODO: better validation
        data, mime_type, charset = decode_data_uri(content, (guessed_mime_type,)*2)
        router.add_http_route(static_content_handler(data, mime_type, charset), path, { "get" })
      else:
        router.add_http_route(static_content_handler(content.encode("utf-8"), guessed_mime_type or "text/plain"), path, { "get" })
    if MetadataFields.ASGISERVER in metadata:
      router.add_handler(ASGIProxyApp(self.client, str_to_endpoint(metadata[MetadataFields.ASGISERVER])))
    return router
