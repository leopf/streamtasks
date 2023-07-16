from abc import ABC, abstractmethod
from typing import Iterable
from streamtasks.asgi import ASGIApp
from streamtasks.client import Client
from streamtasks.system.protocols import *
from streamtasks.system.types import TaskFactoryRegistration, DashboardRegistration, DashboardInfo
from streamtasks.asgi import *
import fnmatch
import urllib.parse
import uvicorn
import re
import asyncio
import httpx

async def asgi_app_not_found(scope, receive, send):
  await send({"type": "http.response.start", "status": 404})
  await send({"type": "http.response.body", "body": b"404 Not Found"})

class ASGIIDRouter:
  def __init__(self):
    self._apps = {}

  def add_app(self, id: str, app: ASGIApp):
    self._apps[id] = app
  def remove_app(self, id: str):
    self._apps.pop(id, None)
  
  async def __call__(self, scope, receive, send):
    if "path" in scope: 
      req_path = scope["path"]
      id = req_path[1:].split("/")[0]
      found_app = self._apps.get(id, None)
      new_scope = dict(scope)
      new_scope["path"] = req_path[len(id)+1:]
      if found_app:
        return await found_app(new_scope, receive, send)
    await asgi_app_not_found(scope, receive, send)

  def get_path_to_id(self, id: str, base_path: str) -> str:
    return urllib.parse.urljoin(base_path, self._sanitize_id(id))

  def _sanitize_id(self, id: str) -> str:
    return urllib.parse.quote(id)

class ASGIServer(ABC):
  @abstractmethod
  async def serve(self, app: ASGIApp): pass

class ASGITestServer(ASGIServer):
  def __init__(self, hostname: str = "testserver"):
    self._app = None
    self._hostname = hostname
    self._waiter = asyncio.Event()
  async def serve(self, app: ASGIApp):
    self._app = app
    self._waiter.set()
  async def wait_for_client(self):
    await self._waiter.wait()
    transport = httpx.ASGITransport(app=self._app)
    client = httpx.AsyncClient(transport=transport, base_url="http://" + self._hostname)
    return client
class UvicornASGIServer(ASGIServer):
  def __init__(self, port: int, host: str = "127.0.0.1"):
    super().__init__()
    self.port = port
    self.host = host
  async def serve(self, app: ASGIApp):
    config = uvicorn.Config(app, port=self.port, host=self.host)
    server = uvicorn.Server(config)
    await server.serve()