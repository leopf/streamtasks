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
from streamtasks.asgiserver import ASGIRouter, ASGIServer, HTTPContext, http_context_handler
from streamtasks.connection import AutoReconnector, ServerBase, connect, get_server
from streamtasks.env import NODE_NAME, get_data_sub_dir
from streamtasks.net import EndpointOrAddress, Link
from streamtasks.services.protocols import AddressNames
from streamtasks.system.task_web import PathRegistrationFrontend, TaskWebPathHandler
import dbm
import urllib.parse
from streamtasks.worker import Worker

URLListAdapter = TypeAdapter(list[str])

T = TypeVar("T", bound=Worker)

def get_url_node_name(): return re.sub("[^a-zA-Z0-9-_]", "", NODE_NAME().lower())

class UrlData(Generic[T]):
  def __init__(self, url: str, worker: T) -> None:
    self.url = url
    self.worker: T = worker
    self.task: asyncio.Task | None = None
  
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
      netloc=purl.hostname + (":" + str(purl.port) if purl.port else ""),
      path=purl.path,
      params="",
      query="",
      fragment=""
    ))

  def start(self):
    if self.task is not None: return
    self.task = asyncio.create_task(self.worker.run())

  async def stop(self):
    if self.task is None: return None
    self.task.cancel()
    try: await self.task
    except asyncio.CancelledError: pass
    finally: self.task = None
    
  @abstractmethod
  def to_json_data(self) -> dict: pass

class ServeUrlData(UrlData[ServerBase]):
  def to_json_data(self): return { "id": self.id, "url": self.sanitized_url, "connection_count": self.worker.connection_count }

class ConnectUrlData(UrlData[AutoReconnector]):
  def to_json_data(self): return { "id": self.id, "url": self.sanitized_url, "connected": self.worker.connected }

class UrlCreateModel(BaseModel):
  url: str

class ConnectionManager(TaskWebPathHandler):
  def __init__(self, link: Link, register_endpoits: list[EndpointOrAddress] = [AddressNames.TASK_MANAGER_WEB]):
    super().__init__(link, f"/connections/{get_url_node_name()}/", PathRegistrationFrontend(path="std:connections", label=f"Connections ({NODE_NAME()})"), register_endpoits)
    self.db = dbm.open(os.path.join(get_data_sub_dir("user-data"), "connections.db"), flag="c")
    self._connect_url_data: list[ConnectUrlData] = []
    self._serve_url_data: list[ServeUrlData] = []
    
  def __del__(self): self.db.close()
  
  def get_connect_urls(self) -> list[str]:
    try: return URLListAdapter.validate_json(self.db.get("connect", b"[]"))
    except ValidationError: return []
  
  def update_connect_urls(self):
    self.db["connect"] = json.dumps([ data.url for data in self._connect_url_data ]).encode("utf-8")
  
  def get_serve_urls(self) -> list[str]:
    try: return URLListAdapter.validate_json(self.db.get("serve", b"[]"))
    except ValidationError: return []
  
  def update_serve_urls(self):
    self.db["serve"] = json.dumps([ data.url for data in self._serve_url_data ]).encode("utf-8")
  
  async def start_serve(self, url: str):
    server = get_server(await self.switch.add_local_connection(), url)
    self._serve_tasks[url] = server
    
  async def run_inner(self):
    try: 
      for url in self.get_connect_urls(): self._connect_url_data.append(await self.create_connect_url_data(url))
      for url in self.get_serve_urls(): self._serve_url_data.append(await self.create_serve_url_data(url))
      for url_data in itertools.chain(self._connect_url_data, self._serve_url_data): url_data.start()
      await self.run_web_server()
    finally:
      for data in itertools.chain(self._connect_url_data, self._connect_url_data): await data.stop()
  
  async def run_web_server(self):
    app = ASGIServer()
    router = ASGIRouter()
    app.add_handler(router)
    
    @app.handler
    @http_context_handler
    async def _(ctx: HTTPContext): 
      await ctx.respond_status(404)
    
    @router.get("/api/connects")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json([ url_data.to_json_data() for url_data in self._connect_url_data ])
    
    @router.delete("/api/connect/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      id = ctx.params.get("id", None)
      data = next((data for data in self._connect_url_data if data.id == id), None)
      if data is None: return await ctx.respond_status(404)
      await data.stop()
      self._connect_url_data = [data for data in self._connect_url_data if data.id != id]
      self.update_connect_urls()
      await ctx.respond_status(200)
    
    @router.post("/api/connect")
    @http_context_handler
    async def _(ctx: HTTPContext):
      req = UrlCreateModel.model_validate_json(await ctx.receive_json_raw())
      data = await self.create_connect_url_data(req.url)
      data.start()
      self._connect_url_data.append(data)
      self.update_connect_urls()
      await ctx.respond_json(data.to_json_data())
    
    @router.get("/api/serves")
    @http_context_handler
    async def _(ctx: HTTPContext): await ctx.respond_json([ url_data.to_json_data() for url_data in self._serve_url_data ])
    
    @router.delete("/api/serve/{id}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      id = ctx.params.get("id", None)
      data = next((data for data in self._serve_url_data if data.id == id), None)
      if data is None: return await ctx.respond_status(404)
      await data.stop()
      self._serve_url_data = [data for data in self._connect_url_data if data.id != id]
      self.update_serve_urls()
      await ctx.respond_status(200)
    
    @router.post("/api/serve")
    @http_context_handler
    async def _(ctx: HTTPContext):
      req = UrlCreateModel.model_validate_json(await ctx.receive_json_raw())
      data = await self.create_serve_url_data(req.url)
      data.start()
      self._serve_url_data.append(data)
      self.update_serve_urls()
      await ctx.respond_json(data.to_json_data())
    
    await ASGIAppRunner(self.client, app).run()
  
  async def create_connect_url_data(self, url: str):
    return ConnectUrlData(url=url, worker=AutoReconnector(link=await self.create_link(), connect_fn=functools.partial(connect, url=url)))

  async def create_serve_url_data(self, url: str):
    return ServeUrlData(url=url, worker=get_server(link=await self.create_link(), url=url))