import base64
import codecs
import functools
from io import BytesIO
import json
import mimetypes
import os
import pathlib
import re
from typing import Any, Awaitable, Callable, Iterable, Literal, NotRequired
from typing_extensions import TypedDict
from collections.abc import ByteString
from urllib.parse import unquote_plus


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

  async def _wsend(self, event: dict): await self._send(event)
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
  def scope(self) -> TransportScope: return { **self._scope }
  @functools.cached_property
  def headers(self):
    res: dict[str, list[str]] = {}
    for k, v in self._scope["headers"]:
      key = k.decode(errors="ignore").lower()
      res[key] = res.get(key, []) + [v.decode(errors="ignore")] # TODO improve this...
    return res
  @functools.cached_property
  def content_type(self):
    ct = self.headers.get("content-type", None)
    if ct is None or len(ct) == 0: raise ValueError("No content type specified on request!")
    if len(ct) > 1: raise ValueError("More than one content-type was specified!")
    ct = ct[0]
    parts = [ p.strip() for p in ct.split(";") ]
    mime_type = parts[0].lower()
    params = { k.lower(): v for k, v in (tuple(p.split("=") for p in parts[1:] if p.count("=") == 1)) }
    return mime_type, params


class WebsocketContext(TransportContext):
  close_reasons = {
    1000: 'Normal Closure', 1001: 'Going Away', 1002: 'Protocol Error',
    1003: 'Unsupported Data', 1004: 'Reserved', 1005: 'No Status Rcvd',
    1006: 'Abnormal Closure', 1007: 'Invalid frame payload data', 1008: 'Policy Violation',
    1009: 'Message too big', 1010: 'Mandatory Ext.', 1011: 'Internal Error',
    1012: 'Service Restart', 1013: 'Try Again Later', 1014: 'Bad Gateway',
    1015: 'TLS Handshake'
  }

  def __init__(self, scope: WebsocketScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    super().__init__(scope, receive, send)
    self._connected = False
    self._accepted = False
    self._add_accept_headers: list[tuple[ByteString, ByteString]] = []
    self._scope: WebsocketScope

  @property
  def connected(self): return self._connected

  @property
  def accepted(self): return self._accepted

  def add_accept_headers(self, headers: Iterable[tuple[ByteString, ByteString]]): self._add_accept_headers.extend(headers)

  async def messages(self, headers: Iterable[tuple[ByteString, ByteString]] = [], subprotocol: str | None = None):
    await self.accept(headers, subprotocol)
    while self._connected:
      event_type, data = await self.receive()
      if event_type == "message" and data is not None: yield data

  async def accept(self, headers: Iterable[tuple[ByteString, ByteString]] = [], subprotocol: str | None = None):
    if self._accepted: return
    if not self._connected:
      event_type, _ = await self.receive()
      if event_type != "connect": raise RuntimeError(f"Expected 'websocket.connect' event. '{event_type}' received.")
    await self.send_accept(headers, subprotocol)

  async def send_accept(self, headers: Iterable[tuple[ByteString, ByteString]] = [], subprotocol: str | None = None):
    await self._wsend({ "type": "websocket.accept", "subprotocol": subprotocol, "headers": [ (name.lower(), value) for name, value in headers ] })

  async def receive_disconnect(self):
    while True:
      event = await self._wreceive()
      if event.get("type", None) == "websocket.disconnect": return

  async def receive(self) -> tuple[Literal["message", "connect", "disconnect"], str | ByteString | None]:
    event = await self._wreceive()
    if event["type"] == "websocket.connect": return "connect", None
    if event["type"] == "websocket.disconnect": return "disconnect", None
    if event["type"] == "websocket.receive": return "message", event.get("bytes", None) or event.get("text", None)

  async def send_message(self, data: str | ByteString):
    event: dict[str, Any] = { "type": "websocket.send", "bytes": None, "text": None }
    if isinstance(data, str): event["text"] = data
    else: event["bytes"] = data
    await self._wsend(event)

  async def close(self, code: int = 1000, reason: str | None = None):
    await self._wsend({ "type": "websocket.close", "code": code, "reason": WebsocketContext.close_reasons.get(code, "") if reason is None else reason })

  async def _wsend(self, event: dict):
    if event["type"] == "websocket.accept":
      self._accepted = True
      event = { **event, "headers": event.get("headers", []) + self._add_accept_headers }
    await super()._wsend(event)

  async def _wreceive(self) -> dict:
    event = await super()._wreceive()
    if event["type"] == "websocket.connect": self._connected = True
    elif event["type"] == "websocket.disconnect": self._connected = False
    return event

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

class HTTPBodyReader:
  def __init__(self, receive: ASGIFnReceive) -> None:
    self._receive = receive
    self._ended = False

  @property
  def ended(self): return self._ended

  async def read_all(self):
    body = BytesIO()
    while not self._ended: body.write(await self.read())
    return body.getvalue()

  async def read(self):
    event = await self._receive()
    event_type = event.get("type", None)
    if event_type == "http.disconnect": self._ended = True
    if event_type == "http.request":
      self._ended = not event.get("more_body", False)
      return event.get("body", b"")
    return b""

class HTTPContext(TransportContext):
  def __init__(self, scope: HTTPScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    super().__init__(scope, receive, send)
    self._connected: bool = True
    self._more_request_body: bool = True
    self._more_response_body: bool = True
    self._add_response_headers: list[tuple[ByteString, ByteString]] = []
    self._scope: HTTPScope

  @property
  def connected(self): return self._connected
  @property
  def more_request_body(self): return self._more_request_body
  @property
  def more_response_body(self): return self._more_response_body
  @property
  def method(self): return self._scope["method"]
  @functools.cached_property
  def body(self): return HTTPBodyReader(self._wreceive)

  def add_response_headers(self, headers: Iterable[tuple[ByteString, ByteString]]): self._add_response_headers.extend(headers)

  async def respond_status(self, status: int): await self.respond_text({ 404: "Not found" }.get(status, "-"), status=status)
  async def respond_json(self, json_data: Any, status: int = 200): await self.respond_json_string(json.dumps(json_data), status=status)
  async def respond_json_string(self, json_string: str, status: int = 200): await self.respond_text(json_string, mime_type="application/json", status=status)
  async def respond_json_raw(self, json_data: bytes, status: int = 200, encoding: str = "utf-8"): await self.respond_buffer(status, json_data, mime_type="application/json", charset=encoding)
  async def respond_text(self, text: str, status: int = 200, mime_type: str = "text/plain"): await self.respond_string(status, text, mime_type)
  async def respond_string(self, status: int, text: str, mime_type: str): await self.respond_buffer(status, text.encode("utf-8"), mime_type, "utf-8")
  async def respond_buffer(self, status: int, content: bytes, mime_type: str, charset: str | None = None):
    content_type = mime_type
    if charset is not None: content_type += f"; charset={charset}"
    writer = await self.respond(status, headers=[
      (b"content-length", str(len(content)).encode("utf-8")),
      (b"content-type", content_type.encode("utf-8"))
    ])
    writer.write(content)
    await writer.close()
  async def respond_file(self, path: str | pathlib.Path, status: int = 200, mime_type: str | None = None, buffer_size: int = -1):
    buffer_size = int(buffer_size)
    st = os.stat(path)
    mime_type = mime_type or mimetypes.guess_type(path)[0]
    if mime_type is None: raise ValueError("Unknown mime type!")

    content_type = mime_type
    writer = await self.respond(status, headers=[
      (b"content-length", str(st.st_size).encode("utf-8")),
      (b"content-type", content_type.encode("utf-8"))
    ])

    with open(path, "rb") as fd:
      while len(buf := fd.read(buffer_size)) == buffer_size:
        writer.write(buf)
        await writer.flush()
      writer.write(buf)
      await writer.flush(close=True)
  async def respond(self, status: int, headers: Iterable[tuple[ByteString, ByteString]], trailers: bool = False):
    await self._wsend({
      "type": "http.response.start",
      "status": status,
      "headers": headers,
      "trailers": trailers
    })
    return HTTPBodyWriter(self._wsend)

  async def receive_json(self): return json.loads(await self.receive_json_raw())
  async def receive_json_raw(self): return await self.receive_text({ "application/json" })
  async def receive_text(self, allowed_mime_types: Iterable[str]):
    allowed_mime_types = allowed_mime_types if isinstance(allowed_mime_types, set) else set(allowed_mime_types)
    mime_type, ct_params = self.content_type
    if mime_type not in allowed_mime_types: raise ValueError(f"Mime type '{mime_type}' is not in allowed types!")
    charset = ct_params.get("charset", "utf-8")
    try: decoder = codecs.getdecoder(charset)
    except LookupError: raise ValueError("Invalid content-type encoding!")
    data = await self.body.read_all()
    return decoder(data, "ignore")[0]

  async def _wsend(self, event: dict):
    event_type = event.get("type", None)
    if event_type == "http.response.start": event = { **event, "headers": event.get("headers", []) + self._add_response_headers }
    if event_type == "http.response.body": self._more_response_body = event.get("more_body", False)
    return await super()._wsend(event)
  async def _wreceive(self) -> dict:
    event = await super()._wreceive()
    event_type = event.get("type", None)
    if event_type == "http.disconnect": self._connected = False
    if event_type == "http.request": self._more_request_body = event.get("more_body", False)
    return event

def http_context_handler(fn: Callable[[HTTPContext], Awaitable[Any]]):
  async def decordator(scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend):
    if scope.get("type", None) != "http": await asgi_scope_get_next_fn(scope)(scope, receive, send)
    else: await fn(HTTPContext(scope, receive, send))
  return decordator

def websocket_context_handler(fn: Callable[[WebsocketContext], Awaitable[Any]]):
  async def decordator(scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend):
    if scope.get("type", None) != "websocket": await asgi_scope_get_next_fn(scope)(scope, receive, send)
    else: await fn(WebsocketContext(scope, receive, send))
  return decordator

def transport_context_handler(fn: Callable[[HTTPContext], Awaitable[Any]]):
  async def decordator(scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend):
    scope_type = scope.get("type", None)
    if scope_type == "http": await fn(HTTPContext(scope, receive, send))
    elif scope_type == "websocket": await fn(WebsocketContext(scope, receive, send))
    else: await asgi_scope_get_next_fn(scope)(scope, receive, send)
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
  def handler(self, handler: ASGIHandler):
    self.add_handler(handler)
    return handler
  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend): await ASGINext(self._handlers)(scope, receive, send)

class ASGIServer(ASGIHandlerStack):
  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    try:
      await super().__call__(scope, receive, send)
    except NoHandlerError:
      if scope.get("type", None) == "http": await HTTPContext(scope, receive, send).respond_status(404)
      elif scope.get("type", None) == "websocket": await WebsocketContext(scope, receive, send).close(reason="No handler found.")
    except BaseException:
      if scope.get("type", None) == "http": await HTTPContext(scope, receive, send).respond_status(500)
      elif scope.get("type", None) == "websocket": await WebsocketContext(scope, receive, send).close(code=1011)

# TODO: matching needs improvements
class PathPattern:
  def __init__(self, pattern: str) -> None:
    pattern = pattern.rstrip("/")
    param_ranges: list[tuple[int, int]] = []
    param_search_start = 0
    while (param_start := pattern.find("{", param_search_start)) != -1:
      param_end = pattern.find("}", param_start)
      if param_end == -1: raise ValueError("Invalid pattern. Expected closing brace after opening brace.")
      param_search_start = param_end
      param_ranges.append((param_start, param_end))

    param_name_regex = re.compile("^[a-zA-Z0-9_]*\\*?$")

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

  def construct(self, params: dict[str, str], default_value: str | None = None) -> str:
    param_parts = []
    for param_name, param_allow_slash in self.params:
      v = params.get(param_name, default_value)
      if v is None: raise ValueError("Param can not be None!")
      if not param_allow_slash and "/" in v: raise ValueError("Found flash in param name, which is not allowed!")
      param_parts.append(v)
    result_parts = []
    for idx in range(len(self.params)):
      result_parts.append(self.parts[idx])
      result_parts.append(param_parts[idx])
    result_parts.append(self.parts[-1])
    return "".join(result_parts)

  def match(self, path: str) -> dict[str,str] | None:
    # path = path.rstrip("/")
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
      current_index += len(param_val)
      if "/" in param_val and not param_allow_slash: return None
      if param_name is not None: params[param_name] = param_val
    return params

class HTTPRoute:
  def __init__(self, handler: ASGIHandler, path_matcher: PathPattern, methods: Iterable[str]) -> None:
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
  def __init__(self, handler: ASGIHandler, path_matcher: PathPattern) -> None:
    self.handler = handler
    self.path_matcher = path_matcher

  @asgi_type_handler({ "websocket" })
  async def __call__(self, scope: WebsocketScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    ctx = WebsocketContext(scope, receive, send)
    if (params := self.path_matcher.match(ctx.path)) is None: return await ctx.next()
    await ctx.delegate(self.handler, asgi_scope_set_state(scope, { SN_PARAMS: params, SN_NEXT_FN: ASGINext([]) }))

class TransportRoute:
  def __init__(self, handler: ASGIHandler, path_matcher: PathPattern) -> None:
    self.handler = handler
    self.path_matcher = path_matcher

  @asgi_type_handler({ "websocket", "http" })
  async def __call__(self, scope: HTTPScope | WebsocketScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    ctx = TransportContext(scope, receive, send)
    if (params := self.path_matcher.match(ctx.path)) is None: return await ctx.next()
    await ctx.delegate(self.handler, asgi_scope_set_state(scope, { SN_PARAMS: params, SN_NEXT_FN: ASGINext([]) }))

class ASGIRouter(ASGIHandlerStack):
  def add_transport_route(self, handler: ASGIHandler, path: str): self.add_handler(TransportRoute(handler, PathPattern(path)))
  def transport_route(self, path: str):
    def decorator(fn: ASGIHandler):
      self.add_transport_route(fn, path)
      return fn
    return decorator

  def add_http_route(self, handler: ASGIHandler, path: str, methods: Iterable[str]):
    self.add_handler(HTTPRoute(handler, PathPattern(path), methods))
  def http_route(self, path: str, methods: Iterable[str]):
    def decorator(fn: ASGIHandler):
      self.add_http_route(fn, path, methods)
      return fn
    return decorator

  def add_websocket_route(self, handler: ASGIHandler, path: str):
    self.add_handler(WebsocketRoute(handler, PathPattern(path)))
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

def path_rewrite(fn: ASGIHandler, pattern: str | PathPattern, default_param_value: str | None = None):
  pattern = PathPattern(pattern) if isinstance(pattern, str) else pattern
  @transport_context_handler
  async def handler(ctx: TransportContext):
    await ctx.delegate(fn, { **ctx.scope, "path": pattern.construct(ctx.params, default_value=default_param_value) })
  return handler

def path_rewrite_handler(pattern: str | PathPattern, default_param_value: str | None = None):
  def decorator(fn: ASGIHandler): return path_rewrite(fn, pattern, default_param_value=default_param_value)
  return decorator

@http_context_handler
async def http_not_found_handler(ctx: HTTPContext): await ctx.respond_status(404)

def static_content_handler(content: ByteString, mime_type: str, charset: str | None = None):
  @http_context_handler
  async def handler(ctx: HTTPContext): await ctx.respond_buffer(200, content, mime_type, charset)
  return handler

def static_file_handler(path: str | pathlib.Path, response_buffer_size=1000_000):
  path = pathlib.Path(path).resolve(strict=True)
  @http_context_handler
  async def handler(ctx: HTTPContext): await ctx.respond_file(path, buffer_size=response_buffer_size)
  return handler

def static_files_handler(path: str | pathlib.Path, index_files: Iterable[str], response_buffer_size=1000_000):
  if any(True for p in index_files if "/" in p or "\\" in p): raise ValueError("Index files can not have a slash!")
  index_files = list(index_files)
  directory_path = pathlib.Path(path).resolve(strict=True)
  if not directory_path.is_dir(): return static_file_handler(path, response_buffer_size=response_buffer_size)

  @http_context_handler
  async def handler(ctx: HTTPContext):
    request_path = directory_path.joinpath(ctx.path.lstrip("/\\")).resolve()
    if directory_path not in request_path.parents and directory_path != request_path: return await ctx.respond_status(404)
    if request_path.is_dir(): request_path = next((p for p in (request_path.joinpath(idx_file) for idx_file in index_files) if p.exists()), None)
    if request_path is None or not request_path.exists() or request_path.is_dir(): return await ctx.respond_status(404)
    await ctx.delegate(static_file_handler(request_path, response_buffer_size=response_buffer_size))

  return handler

def decode_data_uri(data_uri: str, default_mime_types: tuple[str | None, str | None]=(None, None), default_charset="utf-8"):
  if not data_uri.startswith("data:"): raise ValueError("Invalid Data URI: Does not start with 'data:'")
  metadata, encoded_data = data_uri[5:].split(',', 1)
  metadata_parts = metadata.lower().split(';')
  is_base64 = 'base64' in metadata_parts
  mime_type = metadata_parts[0] or ((default_mime_types[1] or "application/octet-stream") if is_base64 else (default_mime_types[0] or "text/plain"))

  if is_base64:
    charset = next((p for p in metadata_parts if p.startswith("charset=")), None)
    if charset is not None: charset = charset[8:].strip()
    byte_data = base64.b64decode(encoded_data)
  else:
    charset = default_charset
    byte_data = unquote_plus(encoded_data).encode(default_charset)

  return byte_data, mime_type, charset
