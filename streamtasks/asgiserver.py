from io import BytesIO
import re
from typing import Any, Awaitable, Callable, Iterable, Literal, NotRequired, TypedDict
from collections.abc import ByteString

class ASGIScope(TypedDict):
  type: Literal["http", "websocket"]
  asgi: dict[Literal["version", "spec_version"], str]
  http_version: str
  method: NotRequired[str] # http only
  scheme: Literal["http", "https", "ws", "wss"]
  path: str
  raw_path: ByteString | None
  query_string: ByteString | None
  root_path: str
  headers: Iterable[tuple[ByteString, ByteString]]
  client: tuple[str, int]
  server: tuple[str, int]
  subprotocols: NotRequired[Iterable[str]] # websocket only
  state: NotRequired[dict[str,Any]]
  
ASGIFnSend = Callable[[dict], Awaitable[Any]]
ASGIFnReceive = Callable[[], Awaitable[dict]]

SN_NEXT_FN = "nextFn"
SN_PARAMS = "params"

ASGIHandler = Callable[[ASGIScope, ASGIFnReceive, ASGIFnSend], Awaitable[Any]]

def asgi_scope_set_state(scope: ASGIScope, state: dict[str, Any]):
  new_scope: ASGIScope = { **scope }
  if not "state" in new_scope: new_scope["state"] = {}
  new_scope["state"].update(state)
  return new_scope

class NotFoundError(BaseException): pass

class HTTPBodyWriter:
  def __init__(self, send: ASGIFnSend) -> None:
    self._send = send
    self._buffer = BytesIO()
    
  def write(self, data: ByteString): self._buffer.write(data)
  async def flush(self, close: bool = False):
    await self._send({
      "type": "http.response.body",
      "body": self._buffer.getvalue(),
      "more_body": not close
    })
    self._buffer.seek(0)
    self._buffer.truncate(0)
  async def close(self): await self.flush(True)
    
class ASGIContext:
  def __init__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    self._scope = scope
    self._receive = receive
    self._send = send
    self._nextHdl: Callable | None = None
    if "state" in scope and SN_NEXT_FN in scope["state"] and callable(scope["state"][SN_NEXT_FN]):
      self._nextHdl = scope["state"][SN_NEXT_FN]
  
  # strip query
  @property
  def path(self): return self._scope["path"]
  # strip query
  @property
  def fullpath(self): return self._scope["rawpath"].decode("utf-8")
  @property
  def method(self): return str(self._scope["method"]).lower() if "method" in self._scope else None
  @property
  def raw_scope(self): return self._scope

  async def delegate(self, app: ASGIHandler, scope: ASGIScope | None = None): await app(scope or self._scope, self._wreceive, self._wsend)
  async def next(self, scope: ASGIScope | None = None): 
    if self._nextHdl is None: raise ValueError("No next handler found in scope!")
    await self.delegate(self._nextHdl, scope)

  async def http_respond(self, status: int, headers: Iterable[tuple[ByteString, ByteString]], trailers: bool = False):
    await self._wsend({
      "type": "http.response.start",
      "status": status,
      "headers": headers,
      "trailers": trailers
    })
    return HTTPBodyWriter(self._wsend)

  async def http_respond_status(self, status: int):
    await self.http_respond_text({ 404: "Not found" }.get(status, "-"), status=status)
  async def http_respond_text(self, text: str, status: int = 200, content_type: str = "text/plain"):
    await self.http_respond_fixed(status, text, content_type)
  async def http_respond_fixed(self, status: int, text: str, content_type: str):
    text = text or "Not found"
    content_type = (content_type or "text/plain") + "; charset=utf-8"
    
    writer = await self.http_respond(status, headers=[
      (b"content-length", str(len(text)).encode("utf-8")),
      (b"content-type", content_type.encode("utf-8"))
    ])
    writer.write(text.encode("utf-8"))
    await writer.close()
  
  async def _wsend(self, data: dict): await self._send(data)
  async def _wreceive(self) -> dict: return await self._receive()

ASGIContextHandler = Callable[['ASGIContext'], Awaitable[Any]]
class ASGIContextHandlerWrapper:
  def __init__(self, handler: ASGIContextHandler) -> None:
    self.handler = handler
  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    return await self.handler(ASGIContext(scope, receive, send))

def asgi_context_handler(fn: ASGIContextHandler): return ASGIContextHandlerWrapper(fn)

class ASGINext:
  def __init__(self, handlers: list[ASGIHandler]) -> None: self._handlers = handlers
  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    if len(self._handlers) == 0: raise NotFoundError()
    new_scope = asgi_scope_set_state(scope, { SN_NEXT_FN: ASGINext(self._handlers[1:]) })
    await self._handlers[0](new_scope, receive, send)

class ASGIHandlerStack:
  def __init__(self) -> None: self._handlers: list[ASGIHandler] = []
  def add_handler(self, handler: ASGIHandler): self._handlers.append(handler) 
  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend): await ASGINext(self._handlers)(scope, receive, send)
    
class ASGIServer(ASGIHandlerStack):
  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    try:
      await super().__call__(scope, receive, send)
    except NotFoundError:
      pass

# TODO: replace with something more powerful and performant
class PathMatcher:
  def __init__(self, pattern: str) -> None:
    param_ranges: list[tuple[int, int]] = []
    param_search_start = 0
    while (param_start := pattern.find("{", param_search_start)) != -1:
      param_end = pattern.find("}", param_start)
      if param_end == -1: raise ValueError("Invalid pattern. Expected closing brace after opening brace.")
      param_search_start = param_end
      param_ranges.append((param_start, param_end))
    
    param_name_regex = re.compile("^[a-zA-Z0-9_]*\*?$")
    
    self.parts: list[str] = []
    self.params: list[tuple[str|None,bool]] = []
    part_start = 0
    for ps, pe in param_ranges:
      self.parts.append(pattern[part_start:ps])
      
      param_txt = pattern[ps+1:pe].strip()
      if not param_name_regex.match(param_txt): raise ValueError("Invalid parameter name.")
      if param_txt.endswith("*"): self.params.append((param_txt[:-1] or None, True))
      else: self.params.append((param_txt or None, False))

      part_start = pe + 1
  
    self.parts.append(pattern[part_start:])
    
    for part in self.parts: 
      if "}" in part: raise ValueError("Invalid pattern. Found closing brace without an opening brace.")

  def match(self, path: str) -> dict[str,str] | None:
    if len(self.parts) == 1:
      return {} if path == self.parts[0] else None
    
    params: dict[str, str] = {}  
    current_index = 0
    for idx in range(0, len(self.parts) - 1):
      part1 = self.parts[idx]
      part2 = self.parts[idx + 1]
      param_name, param_allow_slash = self.params[idx]

      part1_len = len(part1)
      if path[current_index:current_index + part1_len] != part1: return None
      
      current_index += part1_len
      if part2 == "" and idx == len(self.parts) - 2:
        param_val = path[current_index:]
      else:
        part2_start = path.find(part2, current_index)
        if part2_start == -1: return None
        param_val = path[current_index:part2_start]

      if "/" in param_val and not param_allow_slash: return None
      if param_name is not None: params[param_name] = param_val
    return params  
    
class ASGIRoute:
  def __init__(self, handler: ASGIHandler, path_matcher: PathMatcher, methods: Iterable[str]) -> None:
    self.handler = handler
    self.path_matcher = path_matcher
    self.methods = set(m.lower() for m in methods)
  
  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    ctx = ASGIContext(scope, receive, send)
    if ctx.method not in self.methods or \
      (params := self.path_matcher.match(ctx.path)) is None: 
        return await ctx.next()
    await ctx.delegate(self.handler, asgi_scope_set_state(scope, { SN_PARAMS: params, SN_NEXT_FN: ASGINext([]) }))    
    
class ASGIRouter(ASGIHandlerStack):
  def add_route(self, handler: ASGIHandler, path: str, methods: Iterable[str]):
    self.add_handler(ASGIRoute(handler, PathMatcher(path), methods))
  def route(self, path: str, methods: Iterable[str]):
    def decorator(fn: ASGIHandler):
      self.add_route(fn, path, methods)
      return fn
    return decorator
  
  def get(self, path: str): return self.route(path, [ "get" ])
  def head(self, path: str): return self.route(path, [ "head" ])
  def post(self, path: str): return self.route(path, [ "post" ])
  def put(self, path: str): return self.route(path, [ "put" ])
  def delete(self, path: str): return self.route(path, [ "delete" ])
  def connect(self, path: str): return self.route(path, [ "connect" ])
  def options(self, path: str): return self.route(path, [ "options" ])
  def trace(self, path: str): return self.route(path, [ "trace" ])
  def patch(self, path: str): return self.route(path, [ "patch" ])
    
  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    ctx = ASGIContext(scope, receive, send)
    try: return await super().__call__(scope, receive, send)
    except NotFoundError: await ctx.http_respond_status(404)