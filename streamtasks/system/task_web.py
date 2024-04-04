import asyncio
import itertools
import mimetypes
from typing import Any
from uuid import UUID, uuid4
from pydantic import UUID4, Field, TypeAdapter, ValidationError
from streamtasks.asgi import ASGIAppRunner, ASGIProxyApp
from streamtasks.asgiserver import ASGIHandler, ASGIRouter, ASGIServer, HTTPContext, TransportContext, decode_data_uri, http_context_handler, path_rewrite_handler, static_content_handler, static_files_handler, transport_context_handler
from streamtasks.client import Client
from streamtasks.client.discovery import register_address_name, register_topic_space
from streamtasks.net import Link, Switch
from streamtasks.net.utils import str_to_endpoint
from streamtasks.services.protocols import AddressNames
from streamtasks.system.task import MetadataDict, MetadataFields, ModelWithId, TaskHostRegistration, TaskHostRegistrationList, TaskInstance, TaskManagerClient
from streamtasks.worker import Worker


class Deployment(ModelWithId):
  id: UUID4 = Field(default_factory=uuid4)
  label: str
  
class StoredTaskInstance(ModelWithId):
  deployment_id: UUID4
  task_host_id: str
  label: str
  config: dict[str, Any]
  frontendConfig: dict[str, Any]
  inputs: list[MetadataDict]
  outputs: list[MetadataDict]

DeploymentList = TypeAdapter(list[Deployment])
StoredTaskInstanceList = TypeAdapter(list[StoredTaskInstance])

class TaskWebBackendStore:
  def __init__(self) -> None:
    self.deployments: dict[str, str] = {}
    self.tasks: dict[str, str] = {}
  
  async def all_deployments(self) -> list[Deployment]: return [ Deployment.model_validate_json(d) for d in self.deployments.values() ]
  async def get_deployment(self, id: UUID4) -> Deployment: return Deployment.model_validate_json(self.deployments[str(id)])
  async def create_deployment(self, deployment: Deployment) -> Deployment: 
    if str(deployment.id) in self.deployments: raise ValueError("Deployment already exists!")
    self.deployments[str(deployment.id)] = deployment.model_dump_json()
  async def update_deployment(self, deployment: Deployment) -> Deployment: 
    if str(deployment.id) not in self.deployments: raise ValueError("Deployment does not exists!")
    self.deployments[str(deployment.id)] = deployment.model_dump_json()
  async def delete_deployment(self, id: UUID4):
    res = self.deployments.pop(str(id), None)
    if res is None: raise ValueError("Deployment does not exist!")
    
  async def all_tasks(self) -> list[StoredTaskInstance]: return [StoredTaskInstance.model_validate_json(v) for v in self.tasks.values()]
  async def all_tasks_in_deployment(self, deployment_id: UUID4) -> list[StoredTaskInstance]: return [ task for task in await self.all_tasks() if task.deployment_id == deployment_id ]
  async def get_task(self, id: UUID4) -> StoredTaskInstance: return StoredTaskInstance.model_validate_json(self.tasks[str(id)])
  async def create_or_update_task(self, task: StoredTaskInstance) -> StoredTaskInstance: self.tasks[str(task.id)] = task.model_dump_json()
  async def delete_task(self, id: UUID4):
    res = self.tasks.pop(str(id), None)
    if res is None: raise ValueError("Task does not exist!")


class TaskWebBackend(Worker):
  def __init__(self, node_link: Link, switch: Switch | None = None, address_name: str = AddressNames.TASK_MANAGER_WEB, 
               task_manager_address_name: str = AddressNames.TASK_MANAGER, public_path: str | None = None):
    super().__init__(node_link, switch)
    self.task_manager_address_name = task_manager_address_name
    self.address_name = address_name
    self.task_host_asgi_handlers: dict[str, ASGIHandler] = {}
    self.task_asgi_handlers: dict[UUID4, ASGIHandler] = {}
    self.public_path = public_path
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
      await asyncio.gather(self.run_asgi_server())
    finally:
      await self.shutdown()
      
  async def run_asgi_server(self):
    app = ASGIServer()
    
    @app.handler
    @http_context_handler
    async def _error_handler(ctx: HTTPContext):
      try:
        await ctx.next()
      except (ValidationError, KeyError, ValueError) as e:
        await ctx.respond_text(str(e), 400)
      except BaseException as e:
        await ctx.respond_text(str(e), 500)
    
    router = ASGIRouter()
    app.add_handler(router)
    
    @router.get("/api/task-hosts")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json_raw(TaskHostRegistrationList.dump_json(await self.tm_client.list_task_hosts()))

    @router.get("/api/deployments")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json_raw(await self.store.all_deployments())
    
    @router.post("/api/deployment/{id}/start")
    @http_context_handler
    async def _(ctx: HTTPContext):
      tasks = await self.store.all_tasks_in_deployment(UUID(ctx.params.get("id", "")))
      topic_ids = set(itertools.chain.from_iterable((int(output["topic_id"]) for output in task.outputs) for task in tasks))
      topic_space_id, _ = await register_topic_space(self.client, topic_ids)
      
      for task in tasks:
        task_instance = await self.tm_client.start_task(task.task_host_id, task.config, topic_space_id)
    
    @router.get("/api/deployment/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext): return await self.store.get_deployment(UUID(ctx.params.get("id", "")))
    
    @router.post("/api/deployment")
    @http_context_handler
    async def _(ctx: HTTPContext):
      deployment = Deployment.model_validate_json(await ctx.receive_json_raw())
      await self.store.create_deployment(deployment)
      await ctx.respond_json_string(deployment.model_dump_json())
    
    @router.put("/api/deployment")
    @http_context_handler
    async def _(ctx: HTTPContext):
      deployment = Deployment.model_validate_json(await ctx.receive_json_raw())
      await self.store.update_deployment(deployment)
      await ctx.respond_json_string(deployment.model_dump_json())
    
    @router.delete("/api/deployment/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      await self.store.delete_deployment(UUID(ctx.params.get("id", "")))
      await ctx.respond_status(200)
      
    @router.get("/api/deployment/{id}/tasks")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json_raw(StoredTaskInstanceList.dump_json(await self.store.all_tasks_in_deployment(UUID(ctx.params.get("id", "")))))
    
    @router.delete("/api/task/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      await self.store.delete_task(UUID(ctx.params.get("id", "")))
      await ctx.respond_status(200)
      
    @router.put("/api/task")
    @http_context_handler
    async def _(ctx: HTTPContext):
      task = StoredTaskInstance.model_validate_json(await ctx.receive_json_raw())
      await self.store.create_or_update_task(task)
      await ctx.respond_json_string(task.model_dump_json())

    @router.post("/api/deployment/{*}")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_status(200)
    
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
        
    if self.public_path is not None: router.add_handler(static_files_handler(self.public_path, ["index.html"]))
    
    runner = ASGIAppRunner(self.client, app)
    await runner.run()
    
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