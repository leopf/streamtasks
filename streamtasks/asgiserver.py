import functools
from io import BytesIO
import re
from typing import Any, Awaitable, Callable, Iterable, Literal, NotRequired, TypedDict, cast
from collections.abc import ByteString

class ASGIScopeBase(TypedDict):
  asgi: dict[Literal["version", "spec_version"], str]
  state: NotRequired[dict[str,Any]]

class LifespanScope(ASGIScopeBase):
  type: Literal["lifespan"]

class TransportScope(ASGIScopeBase):
  http_version: str
  path: str
  raw_path: ByteString | None
  query_string: ByteString | None
  root_path: str
  headers: Iterable[tuple[ByteString, ByteString]]
  client: tuple[str, int]
  server: tuple[str, int]

class HTTPScope(TransportScope):
  type: Literal["http"]
  scheme: Literal["http", "https"]
  method: str

class WebsocketScope(TransportScope):
  type: Literal["websocket"]
  scheme: Literal["ws", "wss"]
  subprotocols: Iterable[str]
  
ASGIScope = HTTPScope | WebsocketScope | LifespanScope | dict
ASGIFnSend = Callable[[dict], Awaitable[Any]]
ASGIFnReceive = Callable[[], Awaitable[dict]]

SN_NEXT_FN = "nextFn"
SN_PARAMS = "params"

ASGIHandler = Callable[[ASGIScope, ASGIFnReceive, ASGIFnSend], Awaitable[Any]]

def asgi_type_handler(supported_types: set[str]):
  def decorator(fn):
    @functools.wraps(fn)
    async def handler(*args):
      scope, receive, send = tuple(args[:3]) if len(args) == 3 else tuple(args[1:4])
      if not isinstance(scope, dict) or not callable(receive) or not callable(send): raise ValueError("Invalid arguments!")
      if scope.get("type", None) in supported_types: await fn(*args)
      else: await asgi_scope_get_next_fn(scope)(scope, receive, send)
    return handler
  return decorator

def asgi_scope_set_state(scope: ASGIScope, state: dict[str, Any]):
  new_scope: ASGIScope = { **scope }
  if not "state" in new_scope: new_scope["state"] = {}
  new_scope["state"].update(state)
  return new_scope

def asgi_scope_get_next_fn(scope: ASGIScope) -> ASGIHandler:
  if "state" in scope and SN_NEXT_FN in scope["state"] and callable(scope["state"][SN_NEXT_FN]): return scope["state"][SN_NEXT_FN]
  else: return ASGINext([])

class NoHandlerError(BaseException): pass

class ContextBase:
  def __init__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    self._scope = scope
    self._receive = receive
    self._send = send
  
  async def delegate(self, app: ASGIHandler, scope: ASGIScope | None = None): await app(scope or self._scope, self._wreceive, self._wsend)
  async def next(self, scope: ASGIScope | None = None): await self.delegate(asgi_scope_get_next_fn(self._scope), scope)

  async def _wsend(self, data: dict): await self._send(data)
  async def _wreceive(self) -> dict: return await self._receive()

class TransportContext(ContextBase):
  def __init__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    super().__init__(scope, receive, send)
    self._scope: TransportScope
  @property
  def params(self) -> dict[str, str]: return self._scope.get("state", {}).get(SN_PARAMS, {})
  @property
  def path(self): return self._scope["path"]
  @property
  def fullpath(self): return (self._scope["raw_path"] or b"").decode("utf-8").split("&", 1)[0]
  @property
  def scope(self): return { **self._scope }

class WebsocketContext(TransportContext):
  close_reasons = {
    1000: 'Normal Closure', 1001: 'Going Away', 1002: 'Protocol Error',
    1003: 'Unsupported Data', 1004: '(For future)', 1005: 'No Status Received',
    1006: 'Abnormal Closure', 1007: 'Invalid frame payload data', 1008: 'Policy Violation',
    1009: 'Message too big', 1010: 'Missing Extension', 1011: 'Internal Error',
    1012: 'Service Restart', 1013: 'Try Again Later', 1014: 'Bad Gateway',
    1015: 'TLS Handshake'
  }
  
  def __init__(self, scope: WebsocketScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    super().__init__(scope, receive, send)
    self._scope: WebsocketScope
    
  async def send_accept(self, headers: Iterable[tuple[ByteString, ByteString]], subprotocol: str | None = None):
    await self._wsend({ "type": "websocket.accept", "subprotocol": subprotocol, "headers": [ (name.lower(), value) for name, value in headers ] })

  async def receive_connect(self):
    event = await self._wreceive()
    event_type = event.get("type", None)
    if event_type != "websocket.connect": raise ValueError(f"Expected message 'websocket.connect', received '{event_type}'.")

  async def send_message(self, data: str | ByteString):
    event: dict[str, Any] = { "type": "websocket.send", "bytes": None, "text": None }
    if isinstance(data, str): event["text"] = data
    else: event["bytes"] = data
    await self._wsend(event)

  async def close(self, code: int = 1000, reason: str | None = None): 
    await self._wsend({ "type": "websocket.close", "code": code, "reason": WebsocketContext.close_reasons.get(code, "") if reason is None else reason })

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

class HTTPContext(TransportContext):
  def __init__(self, scope: HTTPScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    super().__init__(scope, receive, send)
    self._scope: HTTPScope
  
  @property
  def method(self): return self._scope["method"]
  
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

def http_context_handler(fn: Callable[[HTTPContext], Awaitable[Any]]):
  async def decordator(scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend):
    if scope.get("type", None) != "http": await asgi_scope_get_next_fn(scope)(scope, receive, send)
    else: await fn(HTTPContext(scope, receive, send)) 
  return decordator

class ASGINext:
  def __init__(self, handlers: list[ASGIHandler]) -> None: self._handlers = handlers
  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    if len(self._handlers) == 0: raise NoHandlerError()
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
    except NoHandlerError:
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
    
class HTTPRoute:
  def __init__(self, handler: ASGIHandler, path_matcher: PathMatcher, methods: Iterable[str]) -> None:
    self.handler = handler
    self.path_matcher = path_matcher
    self.methods = set(m.upper() for m in methods)

  @asgi_type_handler({ "http" })
  async def __call__(self, scope: HTTPScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    ctx = HTTPContext(scope, receive, send)
    if ctx.method not in self.methods or \
      (params := self.path_matcher.match(ctx.path)) is None: 
        return await ctx.next()
    await ctx.delegate(self.handler, asgi_scope_set_state(scope, { SN_PARAMS: params, SN_NEXT_FN: ASGINext([]) }))    

class WebsocketRoute:
  def __init__(self, handler: ASGIHandler, path_matcher: PathMatcher) -> None:
    self.handler = handler
    self.path_matcher = path_matcher

  @asgi_type_handler({ "websocket" })
  async def __call__(self, scope: WebsocketScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    ctx = WebsocketContext(scope, receive, send)
    if (params := self.path_matcher.match(ctx.path)) is None: return await ctx.next()
    await ctx.delegate(self.handler, asgi_scope_set_state(scope, { SN_PARAMS: params, SN_NEXT_FN: ASGINext([]) }))  

class ASGIRouter(ASGIHandlerStack):
  def add_http_route(self, handler: ASGIHandler, path: str, methods: Iterable[str]):
    self.add_handler(HTTPRoute(handler, PathMatcher(path), methods))
  def http_route(self, path: str, methods: Iterable[str]):
    def decorator(fn: ASGIHandler):
      self.add_http_route(fn, path, methods)
      return fn
    return decorator
  
  def add_websocket_route(self, handler: ASGIHandler, path: str):
    self.add_handler(WebsocketRoute(handler, PathMatcher(path)))
  def websocket_route(self, path: str):
    def decorator(fn: ASGIHandler):
      self.add_websocket_route(fn, path)
      return fn
    return decorator
  
  def get(self, path: str): return self.http_route(path, [ "get" ])
  def head(self, path: str): return self.http_route(path, [ "head" ])
  def post(self, path: str): return self.http_route(path, [ "post" ])
  def put(self, path: str): return self.http_route(path, [ "put" ])
  def delete(self, path: str): return self.http_route(path, [ "delete" ])
  def connect(self, path: str): return self.http_route(path, [ "connect" ])
  def options(self, path: str): return self.http_route(path, [ "options" ])
  def trace(self, path: str): return self.http_route(path, [ "trace" ])
  def patch(self, path: str): return self.http_route(path, [ "patch" ])
    
  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    try: return await super().__call__(scope, receive, send)
    except NoHandlerError:
      if scope.get("type", None) == "http": await HTTPContext(scope, receive, send).http_respond_status(404)
      elif scope.get("type", None) == "websocket": await WebsocketContext(scope, receive, send).close(reason="No handler found.")