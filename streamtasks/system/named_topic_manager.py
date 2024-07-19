import asyncio
import os
from urllib.parse import unquote
from pydantic import BaseModel, TypeAdapter
from streamtasks.asgi import ASGIAppRunner
from streamtasks.asgiserver import ASGIRouter, ASGIServer, HTTPContext, http_context_handler
from streamtasks.client.discovery import register_address_name
from streamtasks.client.fetch import FetchRequest, FetchServer, new_fetch_body_not_found
from streamtasks.env import get_data_sub_dir
from streamtasks.net import EndpointOrAddress, Link
from streamtasks.pydanticdb import PydanticDB
from streamtasks.services.protocols import AddressNames
from streamtasks.system.task import MetadataDict
from streamtasks.system.task_web import PathRegistrationFrontend, TaskWebPathHandler

class NamedTopicModel(BaseModel):
  name: str
  metadata: MetadataDict

class NamedTopicRequestModel(BaseModel):
  name: str

class NamedTopicResolvedResponseModel(BaseModel):
  topic: int

NamedTopicListModel = TypeAdapter(list[NamedTopicModel])

class NamedTopicManager(TaskWebPathHandler):
  def __init__(self, link: Link, register_endpoits: list[EndpointOrAddress] = [AddressNames.TASK_MANAGER_WEB]):
    super().__init__(link, "/named-topics/", PathRegistrationFrontend(path="std:namedtopicmanager", label="Named Topic Manager"), register_endpoits)
    self.db = PydanticDB(NamedTopicModel, os.path.join(get_data_sub_dir("user-data"), "named-topics.json"))
    self.topic_map: dict[str, int] = {}

  async def run_inner(self):
    await register_address_name(self.client, AddressNames.NAMED_TOPIC_MANAGER)
    await asyncio.gather(self.run_web_server(), self.run_fetch_server())

  async def run_fetch_server(self):
    server = FetchServer(self.client)

    @server.route("list_named_topics")
    async def _(req: FetchRequest): await req.respond(NamedTopicListModel.dump_python(self.db.entries))

    @server.route("get_named_topic")
    async def _(req: FetchRequest):
      try:
        data = NamedTopicRequestModel.model_validate(req.body)
        await req.respond(next(e for e in self.db.entries if e.name == data.name).model_dump())
      except KeyError: await req.respond_error(new_fetch_body_not_found("named topic not found!"))

    @server.route("put_named_topic")
    async def _(req: FetchRequest):
      try:
        data = NamedTopicModel.model_validate(req.body)
        self.db.update([e for e in self.db.entries if e.name != data.name] + [data])
        self.db.save()
        await req.respond(data.model_dump())
      except KeyError: await req.respond_error(new_fetch_body_not_found("named topic not found!"))

    @server.route("delete_named_topic")
    async def _(req: FetchRequest):
      data = NamedTopicRequestModel.model_validate(req.body)
      self.db.update(e for e in self.db.entries if e.name != data.name)
      self.db.save()
      await req.respond(None)

    @server.route("resolve_named_topic")
    async def _(req: FetchRequest):
      data = NamedTopicRequestModel.model_validate(req.body)
      if next((1 for e in self.db.entries if e.name == data.name), None) is None: self.db.update(self.db.entries + [ NamedTopicModel(name=data.name, metadata={}) ])
      if data.name not in self.topic_map: self.topic_map[data.name] = (await self.client.request_topic_ids(1))[0]
      await req.respond(NamedTopicResolvedResponseModel(topic=self.topic_map[data.name]).model_dump())

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
    async def _(ctx: HTTPContext): await ctx.respond_json_raw(NamedTopicListModel.dump_json(self.db.entries))

    @router.put("/api/named-topic")
    @http_context_handler
    async def _(ctx: HTTPContext):
      data = NamedTopicModel.model_validate_json(await ctx.receive_json_raw())
      self.db.update([e for e in self.db.entries if e.name != data.name] + [data])
      self.db.save()
      await ctx.respond_json(data.model_dump())

    @router.get("/api/named-topic/{name}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      try:
        name = unquote(ctx.params["name"])
        await ctx.respond_json(next(e for e in self.db.entries if e.name == name).model_dump())
      except KeyError: await ctx.respond_status(404)

    @router.delete("/api/named-topic/{name}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      try:
        name = unquote(ctx.params["name"])
        self.db.update(e for e in self.db.entries if e.name != name)
        self.db.save()
        await ctx.respond_status(200)
      except KeyError: await ctx.respond_status(404)

    await ASGIAppRunner(self.client, app).run()
