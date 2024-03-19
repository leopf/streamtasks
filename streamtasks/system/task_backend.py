

import asyncio
import mimetypes
from pydantic import UUID4
from streamtasks.asgi import ASGIAppRunner, ASGIProxyApp
from streamtasks.asgiserver import ASGIHandler, ASGIRouter, ASGIServer, HTTPContext, TransportContext, decode_data_uri, http_context_handler, http_not_found_handler, path_rewrite_handler, static_content_handler, transport_context_handler
from streamtasks.client import Client
from streamtasks.net import Link, Switch
from streamtasks.net.utils import str_to_endpoint
from streamtasks.services.protocols import AddressNames
from streamtasks.system.task import MetadataDict, MetadataFields, TMTaskStartRequest, TaskHostRegistration, TaskHostRegistrationList, TaskInstance, TaskManagerClient
from streamtasks.worker import Worker

class ASGITaskManagementBackend(Worker):
  def __init__(self, node_link: Link, switch: Switch | None = None, task_manager_address_name: str = AddressNames.TASK_MANAGER):
    super().__init__(node_link, switch)
    self.task_manager_address_name = task_manager_address_name
    self.task_host_asgi_handlers: dict[str, ASGIHandler] = {}
    self.task_asgi_handlers: dict[UUID4, ASGIHandler] = {}
    self.client: Client
    self.tm_client: TaskManagerClient
  
  async def run(self):
    try:
      await self.setup()
      self.client = await self.create_client()
      self.client.start()
      await self.client.request_address()
      # TODO: register a name?
      self.tm_client = TaskManagerClient(self.client, self.task_manager_address_name)
      await asyncio.gather(self.run_asgi_server())
    finally:
      await self.shutdown()
      
  async def run_asgi_server(self):
    app = ASGIServer()
    router = ASGIRouter()
    app.add_handler(router)
    
    @router.get("/api/task-hosts")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json(TaskHostRegistrationList.dump_python(await self.tm_client.list_task_hosts()))
    
    @router.post("/api/task/start")
    @http_context_handler
    async def _(ctx: HTTPContext):
      req = TMTaskStartRequest(**(await ctx.receive_json()))
      task_instance = await self.tm_client.start_task(req.host_id, req.config)
      await ctx.respond_json(task_instance.model_dump())
    
    @router.post("/api/task/stop/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      id = UUID4(ctx.params.get("id", ""))
      task_instance = await self.tm_client.cancel_task_wait(id)
      await ctx.respond_json(task_instance.model_dump())
    
    @router.post("/api/task/cancel/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      id = UUID4(ctx.params.get("id", ""))
      await self.tm_client.cancel_task(id)
      await ctx.respond_status(200)

    @router.http_route("/task/{id}/{path*}", methods=[]) # TODO: more abstract way of doing this
    @path_rewrite_handler
    @transport_context_handler
    async def _(ctx: TransportContext):
      id: UUID4 = UUID4(ctx.params.get("id", ""))
      await ctx.delegate(await self.get_task_asgi_handler(id))

    @router.http_route("/task-host/{id}/{path*}", methods=[]) # TODO: more abstract way of doing this
    @path_rewrite_handler
    @transport_context_handler
    async def _(ctx: TransportContext):
      id = ctx.params.get("id", "")
      await ctx.delegate(await self.get_task_host_asgi_handler(id))
    
    runner = ASGIAppRunner(self.client, app)
    await runner.run()
    
  async def get_task_host_asgi_handler(self, id: str) -> ASGIHandler:
    if (router := self.task_host_asgi_handlers.get(id, None)) is None:
      reg: TaskHostRegistration = await self.tm_client.get_task_host(id)
      self.task_host_asgi_handlers[id] = router = self._metadata_to_router(reg.metadata)
    return router

  async def get_task_asgi_handler(self, id: UUID4) -> ASGIHandler:
    if (router := self.task_asgi_handlers.get(id, None)) is None:
      reg: TaskInstance = await self.tm_client.get_task_host(id)
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