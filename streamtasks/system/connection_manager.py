from abc import abstractmethod
import asyncio
import functools
import hashlib
import itertools
import json
import os
import re
from typing import Generic, TypeVar
from pydantic import BaseModel, TypeAdapter, ValidationError
from streamtasks.asgi import ASGIAppRunner
from streamtasks.asgiserver import ASGIRouter, ASGIServer, HTTPContext, WebsocketContext, http_context_handler, websocket_context_handler
from streamtasks.connection import AutoReconnector, ServerBase, connect, get_server
from streamtasks.env import NODE_NAME, get_data_sub_dir
from streamtasks.net import EndpointOrAddress, Link
from streamtasks.services.protocols import AddressNames
from streamtasks.system.task_web import PathRegistrationFrontend, TaskWebPathHandler
import dbm
import urllib.parse
from streamtasks.utils import AsyncTrigger, wait_with_dependencies
from streamtasks.worker import Worker

URLListAdapter = TypeAdapter(list[str])

T = TypeVar("T", bound=Worker)

def get_url_node_name(): return re.sub("[^a-zA-Z0-9-_]", "", NODE_NAME().lower())

class UrlData(Generic[T]):
  def __init__(self, url: str, worker: T, change_trigger: AsyncTrigger) -> None:
    self.url = url
    self.worker: T = worker
    self.task: asyncio.Task | None = None
    self.change_trigger = change_trigger

  @functools.cached_property
  def id(self):
    id_hash = hashlib.sha256()
    id_hash.update(b"url:::")
    id_hash.update(self.url.encode("utf-8"))
    return id_hash.hexdigest()[:16]

  @functools.cached_property
  def sanitized_url(self):
    purl = urllib.parse.urlparse(self.url)
    if len(purl.scheme) == 0: return self.url
    return urllib.parse.urlunparse(urllib.parse.ParseResult(
      scheme=purl.scheme,
      netloc=(purl.hostname or "") + (":" + str(purl.port) if purl.port else ""),
      path=purl.path,
      params="",
      query="",
      fragment=""
    ))

  @property
  def running(self): return self.task is not None and not self.task.done()

  def start(self):
    if self.task is not None: return
    self.task = asyncio.create_task(self.run())

  async def run(self): await asyncio.gather(self.worker.run(), self.change_handler())
  async def stop(self):
    if self.task is None: return None
    self.task.cancel()
    try: await self.task
    except asyncio.CancelledError: pass
    finally: self.task = None

  @abstractmethod
  def to_json_data(self) -> dict: pass

  @abstractmethod
  async def change_handler(self): pass

class ServerUrlData(UrlData[ServerBase]):
  def to_json_data(self): return { "id": self.id, "url": self.sanitized_url, "running": self.running, "connection_count": self.worker.connection_count }
  async def change_handler(self):
    while True:
      await self.worker.wait_connections_changed()
      self.change_trigger.trigger()

class ConnectionUrlData(UrlData[AutoReconnector]):
  def to_json_data(self): return { "id": self.id, "url": self.sanitized_url, "running": self.running, "connected": self.worker.connected }
  async def change_handler(self):
    while True:
      await self.worker.wait_connected(True)
      self.change_trigger.trigger()
      await self.worker.wait_connected(False)
      self.change_trigger.trigger()

class UrlCreateModel(BaseModel):
  url: str

class ConnectionManager(TaskWebPathHandler):
  def __init__(self, link: Link, register_endpoits: list[EndpointOrAddress] = [AddressNames.TASK_MANAGER_WEB]):
    super().__init__(link, f"/connections/{get_url_node_name()}/", PathRegistrationFrontend(path="std:connectionmanager", label=f"Connections ({NODE_NAME()})"), register_endpoits)
    self.db = dbm.open(os.path.join(get_data_sub_dir("user-data"), "connections.db"), flag="c")
    self._connection_url_data: list[ConnectionUrlData] = []
    self._server_url_data: list[ServerUrlData] = []
    self._change_trigger_servers = AsyncTrigger()
    self._change_trigger_connections = AsyncTrigger()

  def __del__(self): self.db.close()

  def get_connection_urls(self) -> list[str]:
    try: return URLListAdapter.validate_json(self.db.get("connection", b"[]"))
    except ValidationError: return []

  def update_connection_urls(self):
    self.db["connection"] = json.dumps([ data.url for data in self._connection_url_data ]).encode("utf-8")

  def get_server_urls(self) -> list[str]:
    try: return URLListAdapter.validate_json(self.db.get("server", b"[]"))
    except ValidationError: return []

  def update_server_urls(self):
    self.db["server"] = json.dumps([ data.url for data in self._server_url_data ]).encode("utf-8")

  async def run_inner(self):
    try:
      for url in self.get_connection_urls(): self._connection_url_data.append(await self.create_connection_url_data(url))
      for url in self.get_server_urls(): self._server_url_data.append(await self.create_server_url_data(url))
      for url_data in itertools.chain(self._connection_url_data, self._server_url_data): url_data.start()
      await self.run_web_server()
    finally:
      for data in itertools.chain(self._connection_url_data, self._connection_url_data): await data.stop()

  async def run_web_server(self):
    app = ASGIServer()
    router = ASGIRouter()
    app.add_handler(router)

    @app.handler
    @http_context_handler
    async def _(ctx: HTTPContext):
      await ctx.respond_status(404)

    @router.get("/api/connections")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json([ url_data.to_json_data() for url_data in self._connection_url_data ])

    @router.delete("/api/connection/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      id = ctx.params.get("id", None)
      data = next((data for data in self._connection_url_data if data.id == id), None)
      if data is None: return await ctx.respond_status(404)
      await data.stop()
      self._connection_url_data = [data for data in self._connection_url_data if data.id != id]
      self.update_connection_urls()
      await ctx.respond_status(200)

    @router.post("/api/connection")
    @http_context_handler
    async def _(ctx: HTTPContext):
      req = UrlCreateModel.model_validate_json(await ctx.receive_json_raw())
      data = await self.create_connection_url_data(req.url)
      if any(True for connection in self._connection_url_data if connection.id == data.id): return await ctx.respond_status(400)
      data.start()
      self._connection_url_data.append(data)
      self.update_connection_urls()
      await ctx.respond_json(data.to_json_data())

    @router.get("/api/servers")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json([ url_data.to_json_data() for url_data in self._server_url_data ])

    @router.delete("/api/server/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      id = ctx.params.get("id", None)
      data = next((data for data in self._server_url_data if data.id == id), None)
      if data is None: return await ctx.respond_status(404)
      await data.stop()
      self._server_url_data = [data for data in self._server_url_data if data.id != id]
      self.update_server_urls()
      await ctx.respond_status(200)

    @router.post("/api/server")
    @http_context_handler
    async def _(ctx: HTTPContext):
      req = UrlCreateModel.model_validate_json(await ctx.receive_json_raw())
      data = await self.create_server_url_data(req.url)
      if any(True for server in self._server_url_data if server.id == data.id): return await ctx.respond_status(400)
      data.start()
      self._server_url_data.append(data)
      self.update_server_urls()
      await ctx.respond_json(data.to_json_data())

    async def _ws_server_change_handler(ctx: WebsocketContext, receive_disconnect_task: asyncio.Task):
      while ctx.connected:
        await wait_with_dependencies(self._change_trigger_servers.wait(), [receive_disconnect_task])
        await ctx.send_message("server")

    async def _ws_connection_change_handler(ctx: WebsocketContext, receive_disconnect_task: asyncio.Task):
      while ctx.connected:
        await wait_with_dependencies(self._change_trigger_connections.wait(), [receive_disconnect_task])
        await ctx.send_message("connection")

    @router.websocket_route("/on-change")
    @websocket_context_handler
    async def _(ctx: WebsocketContext):
      try:
        await ctx.accept()
        receive_disconnect_task = asyncio.create_task(ctx.receive_disconnect())
        await asyncio.gather(_ws_connection_change_handler(ctx, receive_disconnect_task), _ws_server_change_handler(ctx, receive_disconnect_task))
      finally:
        receive_disconnect_task.cancel()
        await ctx.close()

    await ASGIAppRunner(self.client, app).run()

  async def create_connection_url_data(self, url: str):
    return ConnectionUrlData(url=url, worker=AutoReconnector(link=await self.create_link(), connect_fn=functools.partial(connect, url=url)), change_trigger=self._change_trigger_connections)

  async def create_server_url_data(self, url: str):
    return ServerUrlData(url=url, worker=get_server(link=await self.create_link(), url=url), change_trigger=self._change_trigger_servers)
