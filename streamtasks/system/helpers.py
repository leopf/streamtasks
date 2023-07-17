from abc import ABC, abstractmethod
from streamtasks.asgi import ASGIApp
from streamtasks.system.protocols import *
from streamtasks.system.types import TaskStreamBase, SystemLogEntry
from streamtasks.asgi import *
import urllib.parse
import uvicorn
import asyncio
import httpx
import logging

async def asgi_app_not_found(scope, receive, send):
  await send({"type": "http.response.start", "status": 404})
  await send({"type": "http.response.body", "body": b"404 Not Found"})

def apply_task_stream_config(target: TaskStreamBase, source: TaskStreamBase):
  target.content_type = source.content_type
  target.encoding = source.encoding
  target.extra = source.extra

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
      new_scope["root_path"] = scope["root_path"] + "/" + id
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

class JsonLogger(logging.StreamHandler):
  def __init__(self, stream=None):
    super().__init__(stream)
    self.log_entries = []

  def emit(self, record):
    entry = SystemLogEntry(
      level=record.levelname,
      message=self.format(record),
      timestamp=int(record.created * 1000)
    )
    self.log_entries.append(entry)