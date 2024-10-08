from streamtasks.asgiserver import HTTPContext, http_context_handler
from streamtasks.client.receiver import Receiver
from streamtasks.client.fetch import FetchError, FetchErrorStatusCode, FetchRequest, FetchServer
from streamtasks.utils import AsyncTaskManager
from streamtasks.net import Endpoint, EndpointOrAddress, endpoint_or_address_to_endpoint
from streamtasks.net.messages import AddressedMessage, Message
from streamtasks.net.serialization import RawData
from pydantic import BaseModel, ValidationError
from abc import ABC
from dataclasses import dataclass
import asyncio
import logging
from typing import TYPE_CHECKING, Any, Awaitable, Optional, Callable, ClassVar
from streamtasks.services.constants import NetworkPorts
from streamtasks.worker import Worker

if TYPE_CHECKING:
  from streamtasks.client import Client


@dataclass
class ASGIConnectionConfig:
  scope: dict
  port: int
  remote_endpoint: Endpoint


class ASGIConstants:
  FD_DESCRIPTOR = "init"


class ASGIInitRequest(BaseModel):
  address: int
  port: int
  scope: dict


class ASGIInitResponse(BaseModel):
  port: int


class ASGIEventMessage(BaseModel):
  closed: Optional[bool] = None
  events: list[dict]


# type of an asgi application
ASGIApp = Callable[[dict, Callable[[dict], Awaitable[None]], Callable[[], Awaitable[dict]]], Awaitable[None]]


class ValueTransformer(ABC):
  supported_types: ClassVar[list[type]]

  @classmethod
  def annotate_value(cls, value: Any) -> dict:
    value_type = type(value)
    native_support = value_type in cls.supported_types and not isinstance(value, list)

    if native_support:
      if isinstance(value, dict): return { k: cls.annotate_value(v) for k, v in value.items() }
      elif isinstance(value, tuple): return tuple(cls.annotate_value(v) for v in value)
      elif isinstance(value, set): return set(cls.annotate_value(v) for v in value)
      else: return value
    else:
      if isinstance(value, list): return ["list", [cls.annotate_value(v) for v in value]]
      elif isinstance(value, dict): return ["dict", { k: cls.annotate_value(v) for k, v in value.items() }]
      elif isinstance(value, tuple): return ["tuple", [cls.annotate_value(v) for v in value]]
      elif isinstance(value, set): return ["set", [cls.annotate_value(v) for v in value]]
      elif isinstance(value, bytes) or isinstance(value, bytearray): return ["bytes", value.hex()]
      elif isinstance(value, int): return ["int", value]
      elif isinstance(value, float): return ["float", value]
      elif isinstance(value, bool): return ["bool", value]
      elif isinstance(value, str): return ["str", value]
      elif isinstance(value, type(None)): return ["none"]
      else: return ["unknown"] # TODO: raise?

  @classmethod
  def deannotate_value(cls, value: Any):
    if isinstance(value, list):
      if value[0] == "list": return [cls.deannotate_value(v) for v in value[1]]
      elif value[0] == "dict": return { k: cls.deannotate_value(v) for k, v in value[1].items() }
      elif value[0] == "tuple": return tuple([cls.deannotate_value(v) for v in value[1]])
      elif value[0] == "set": return set([cls.deannotate_value(v) for v in value[1]])
      elif value[0] == "bytes": return bytes.fromhex(value[1])
      elif value[0] == "int": return int(value[1])
      elif value[0] == "float": return float(value[1])
      elif value[0] == "bool": return bool(value[1])
      elif value[0] == "str": return str(value[1])
      elif value[0] == "none": return None
      elif value[0] == "unknown": return None
      else: return value
    elif isinstance(value, dict): return { k: cls.deannotate_value(v) for k, v in value.items() }
    elif isinstance(value, tuple): return tuple(cls.deannotate_value(v) for v in value)
    elif isinstance(value, set): return set(cls.deannotate_value(v) for v in value)
    else: return value


class JSONValueTransformer(ValueTransformer):
  supported_types = [str, int, float, bool, list, dict]


class MessagePackValueTransformer(ValueTransformer):
  supported_types = [str, int, float, bool, bytes, bytearray, list, dict]


class ASGIEventReceiver(Receiver[ASGIEventMessage]):
  def __init__(self, client: 'Client', recv_port: int):
    super().__init__(client)
    self._recv_port = recv_port

  def on_message(self, message: Message):
    if not isinstance(message, AddressedMessage): return
    if message.port != self._recv_port: return
    if not isinstance(message.data, RawData): return
    try: self._recv_queue.put_nowait(ASGIEventMessage.model_validate(message.data.data))
    except ValidationError: pass

class ASGIEventSender:
  def __init__(self, client: 'Client', remote_endpoint: Endpoint):
    self._client = client
    self._remote_endpoint = remote_endpoint
  async def send(self, event: dict): await self._send(events=[event])
  async def close(self):
    await self._send(events=[], closed=True)
  async def _send(self, events: list[dict], closed: Optional[bool] = None):
    events = [MessagePackValueTransformer.annotate_value(event) for event in events]
    await self._client.send_to(self._remote_endpoint, RawData(ASGIEventMessage(events=events, closed=closed).model_dump()))


class ASGIAppRunner:
  def __init__(self, client: 'Client', app: ASGIApp, port: int = NetworkPorts.ASGI):
    if client.address is None: raise Exception("The client must have at least one address to host an ASGI application")
    self._client = client
    self._app = app
    self._port = port
    self._connection_tasks = AsyncTaskManager()

  async def run(self):
    try:
      server = FetchServer(self._client, self._port)

      @server.route(ASGIConstants.FD_DESCRIPTOR)
      async def _(raw_request: FetchRequest):
        init_request = ASGIInitRequest.model_validate(raw_request.body)
        config = ASGIConnectionConfig(
          scope=JSONValueTransformer.deannotate_value(init_request.scope),
          port=self._client.get_free_port(),
          remote_endpoint=(init_request.address, init_request.port))

        self._start_connection(config)
        await raw_request.respond(ASGIInitResponse(port=config.port).model_dump())

      await server.run()

    finally:
      await self._connection_tasks.cancel_all()

  def _start_connection(self, config: ASGIConnectionConfig):
    receiver = ASGIEventReceiver(self._client, config.port)
    stop_signal = asyncio.Event()
    sender = ASGIEventSender(self._client, config.remote_endpoint)

    recv_queue = asyncio.Queue()

    async def send(event: dict):
      await sender.send(event)
      await asyncio.sleep(0)

    async def receive() -> dict:
      while recv_queue.empty() and not stop_signal.is_set():
        data = await receiver.get()
        for event in data.events:
          event = MessagePackValueTransformer.deannotate_value(event)
          await recv_queue.put(event)
      await asyncio.sleep(0)
      return await recv_queue.get()

    async def run():
      try:
        logging.info(f"ASGI instance ({config.port}) starting!")
        async with receiver:
          await self._app(config.scope, receive, send)
      finally:
        await sender.close()
        stop_signal.set()
        logging.info(f"ASGI instance ({config.port}) finished!")

    self._connection_tasks.create(run())

class ASGIProxyApp:
  def __init__(self, client: 'Client', remote_endpoint: EndpointOrAddress):
    if client.address is None: raise Exception("The client must have at least one address to host an ASGI application")
    self._client = client
    self._remote_endpoint = endpoint_or_address_to_endpoint(remote_endpoint, NetworkPorts.ASGI)
  async def __call__(self, scope, receive: Callable[[], Awaitable[dict]], send: Callable[[dict], Awaitable[None]]):
    ser_scope = JSONValueTransformer.annotate_value(scope)

    port = self._client.get_free_port()
    receiver = ASGIEventReceiver(self._client, port)
    await receiver.start_recv() # NOTE: must be enabled before sending init message, otherwise events will be lost

    init_respose_raw = await self._client.fetch(self._remote_endpoint, ASGIConstants.FD_DESCRIPTOR, ASGIInitRequest(
      address=self._client.address,
      port=port,
      scope=ser_scope).model_dump())
    init_respose = ASGIInitResponse.model_validate(init_respose_raw)

    closed_event = asyncio.Event()
    sender = ASGIEventSender(self._client, (self._remote_endpoint[0], init_respose.port))

    async def recv_loop():
      while not closed_event.is_set():
        event = await receive()
        await sender.send(event)
        await asyncio.sleep(0)
        event_type = event.get("type", None)
        if event_type == "http.disconnect" or event_type == "websocket.disconnect": closed_event.set()

    async def send_loop():
      while not closed_event.is_set():
        await asyncio.sleep(0)
        data = await receiver.get()
        for event in data.events: await send(MessagePackValueTransformer.deannotate_value(event))
        if data.closed: closed_event.set()

    recv_task = asyncio.create_task(recv_loop())
    send_task = asyncio.create_task(send_loop())
    await closed_event.wait()
    await receiver.stop_recv()
    recv_task.cancel()
    send_task.cancel()

class HTTPServerOverASGI(Worker):
  def __init__(self, http_endpoint: tuple[str, int], asgi_endpoint: EndpointOrAddress, http_config: dict[str, Any] = {}):
    super().__init__()
    import uvicorn
    self.server: uvicorn.Server | None = None
    self.asgi_endpoint = endpoint_or_address_to_endpoint(asgi_endpoint, NetworkPorts.ASGI)
    self.http_endpoint = http_endpoint
    self.http_config = http_config
  async def run(self):
    try:
      client = await self.create_client()
      client.start()
      await client.request_address()
      app = ASGIProxyApp(client, self.asgi_endpoint)
      import uvicorn
      server_config = uvicorn.Config(app, host=self.http_endpoint[0], port=self.http_endpoint[1], **self.http_config)
      self.server = uvicorn.Server(server_config)
      logging.info(f"Serving [{self.asgi_endpoint[0]}, {self.asgi_endpoint[1]}] on http://{self.http_endpoint[0]}:{self.http_endpoint[1]}/")
      await self.server.serve()
    finally:
      await self.shutdown()

async def asgi_app_not_found(_scope, _receive, send):
  await send({"type": "http.response.start", "status": 404})
  await send({"type": "http.response.body", "body": b"404 Not Found"})

@http_context_handler
async def asgi_default_http_error_handler(ctx: HTTPContext):
  try:
    await ctx.next()
  except (ValidationError, ValueError) as e:
    logging.debug("ASGI request error (bad request): ", e)
    await ctx.respond_status(400)
  except KeyError as e:
    logging.debug("ASGI request error (not found): ", e)
    await ctx.respond_status(404)
  except FetchError as e:
    logging.debug("ASGI request error (fetch error): ", e)
    if e.status_code == FetchErrorStatusCode.NOT_FOUND: await ctx.respond_status(404)
    if e.status_code == FetchErrorStatusCode.BAD_REQUEST: await ctx.respond_status(400)
    if e.status_code == FetchErrorStatusCode.GENERAL: await ctx.respond_status(500)
  except BaseException as e:
    logging.debug("ASGI request error (unknown): ", e)
    await ctx.respond_status(500)
