import asyncio
import os
from pydantic import BaseModel
from streamtasks.asgi import ASGIAppRunner
from streamtasks.asgiserver import ASGIRouter, ASGIServer, HTTPContext, http_context_handler
from streamtasks.client.discovery import register_address_name
from streamtasks.client.fetch import FetchRequest, FetchServer
from streamtasks.env import get_data_sub_dir
from streamtasks.net import EndpointOrAddress, Link
from streamtasks.services.protocols import AddressNames
from streamtasks.system.task import MetadataDict
from streamtasks.system.task_web import PathRegistrationFrontend, TaskWebPathHandler
import dbm

class NamedTopicModel(BaseModel):
  name: str
  metadata: MetadataDict

class NamedTopicManager(TaskWebPathHandler):
  def __init__(self, link: Link, register_endpoits: list[EndpointOrAddress] = [AddressNames.TASK_MANAGER_WEB]):
    super().__init__(link, "/named-topics", PathRegistrationFrontend(path="std:namedtopicmanager", label="Named Topic Manager"), register_endpoits)
    self.db = dbm.open(os.path.join(get_data_sub_dir("user-data"), "named-topics.db"), flag="c")

  def __del__(self): self.db.close()

  async def run_inner(self):
    await register_address_name(self.client, AddressNames.NAMED_TOPIC_MANAGER)
    await asyncio.gather(self.run_web_server(), self.run_fetch_server())

  async def run_fetch_server(self):
    server = FetchServer(self.client)

    @server.route("list_named_topics")
    async def _(req: FetchRequest): pass

    @server.route("get_named_topic")
    async def _(req: FetchRequest): pass

    @server.route("resolve_named_topic")
    async def _(req: FetchRequest): pass

    await server.run()

  async def run_web_server(self):
    app = ASGIServer()
    router = ASGIRouter()
    app.add_handler(router)

    @app.handler
    @http_context_handler
    async def _(ctx: HTTPContext):
      await ctx.respond_status(404)

    @router.get("/api/named-topics")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json([  ])

    @router.delete("/api/named-topics/{name}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      await ctx.respond_status(200)

    @router.post("/api/named-topic")
    @http_context_handler
    async def _(ctx: HTTPContext):
      req = NamedTopicModel.model_validate_json(await ctx.receive_json_raw())
      await ctx.respond_json(req.model_dump())

    await ASGIAppRunner(self.client, app).run()
