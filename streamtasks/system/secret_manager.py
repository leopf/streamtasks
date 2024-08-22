import asyncio
import os
from uuid import UUID
from pydantic import UUID4, BaseModel, TypeAdapter
from streamtasks.asgi import ASGIAppRunner, asgi_default_http_error_handler
from streamtasks.asgiserver import ASGIRouter, ASGIServer, HTTPContext, http_context_handler
from streamtasks.client import Client
from streamtasks.client.discovery import register_address_name
from streamtasks.client.fetch import FetchRequest, FetchServer, new_fetch_body_not_found
from streamtasks.env import get_data_sub_dir
from streamtasks.net import EndpointOrAddress
from streamtasks.pydanticdb import PydanticDB
from streamtasks.services.constants import NetworkAddressNames
from streamtasks.system.task_web import TaskWebPathHandler

class SecretModel(BaseModel):
  id: UUID4
  value: str

class SecretRequestModel(BaseModel):
  id: UUID4

SecretModelListModel = TypeAdapter(list[SecretModel])

class SecretManager(TaskWebPathHandler):
  def __init__(self, register_endpoits: list[EndpointOrAddress] = [NetworkAddressNames.TASK_MANAGER_WEB]):
    super().__init__("/secrets/", register_endpoits=register_endpoits)
    self.db = PydanticDB(SecretModel, os.path.join(get_data_sub_dir("user-data"), "secrets.json"))

  async def run_inner(self):
    await register_address_name(self.client, NetworkAddressNames.NAMED_TOPIC_MANAGER)
    await asyncio.gather(self.run_web_server(), self.run_fetch_server())

  async def run_fetch_server(self):
    server = FetchServer(self.client)

    @server.route("get_secret")
    async def _(req: FetchRequest):
      try:
        data = SecretRequestModel.model_validate(req.body)
        await req.respond(next(e for e in self.db.entries if e.id == data.id).model_dump())
      except KeyError: await req.respond_error(new_fetch_body_not_found("secret not found!"))

    @server.route("put_secret")
    async def _(req: FetchRequest):
      data = SecretModel.model_validate(req.body)
      self.db.update([e for e in self.db.entries if e.id != data.id] + [data])
      self.db.save()
      await req.respond(data.model_dump())

    @server.route("delete_secret")
    async def _(req: FetchRequest):
      data = SecretRequestModel.model_validate(req.body)
      self.db.update(e for e in self.db.entries if e.id != data.id)
      self.db.save()
      await req.respond(None)

    await server.run()

  async def run_web_server(self):
    app = ASGIServer()
    app.add_handler(asgi_default_http_error_handler)

    router = ASGIRouter()
    app.add_handler(router)

    @app.handler
    @http_context_handler
    async def _(ctx: HTTPContext):
      await ctx.respond_status(404)

    @router.put("/api/secret")
    @http_context_handler
    async def _(ctx: HTTPContext):
      data = SecretModel.model_validate_json(await ctx.receive_json_raw())
      self.db.update([e for e in self.db.entries if e.id != data.id] + [data])
      self.db.save()
      await ctx.respond_status(200)

    @router.delete("/api/secret/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      try:
        id = UUID(ctx.params["id"])
        self.db.update(e for e in self.db.entries if e.id != id)
        self.db.save()
        await ctx.respond_status(200)
      except KeyError: await ctx.respond_status(404)

    await ASGIAppRunner(self.client, app).run()

class SecretManagerClient:
  def __init__(self, client: Client, address_name: str = NetworkAddressNames.SECRET_MANAGER) -> None:
    self.address_name = address_name
    self.client = client

  async def resolve_secret(self, id: UUID4):
    result = await self.client.fetch(self.address_name, "get_secret", SecretRequestModel(id=id).model_dump())
    return SecretModel.model_validate(result).value

  async def delete_secret(self, id: UUID4):
    await self.client.fetch(self.address_name, "delete_secret", SecretRequestModel(id=id).model_dump())

  async def put_secret(self, id: UUID4, value: str):
    await self.client.fetch(self.address_name, "put_secret", SecretModel(id=id, value=value).model_dump())
