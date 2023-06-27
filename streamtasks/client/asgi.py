from streamtasks.client.receiver import Receiver
from streamtasks.client.fetch import FetchRequestReceiver, FetchRequest
from streamtasks.comm.types import AddressedMessage, Message
from streamtasks.comm.serialization import MessagePackData
from pydantic import BaseModel
from abc import ABC
from dataclasses import dataclass
import asyncio
import logging
from uuid import uuid4
from typing import TYPE_CHECKING, Any, Awaitable, Optional, Callable, ClassVar

if TYPE_CHECKING:
    from streamtasks.client import Client

@dataclass
class ASGIConnectionConfig:
  scope: dict
  connection_id: str
  remote_address: int
  own_address: int

class ASGIInitMessage(BaseModel):
  connection_id: str
  return_address: int
  scope: dict

class ASGIEventMessage(BaseModel):
  connection_id: str
  closed: Optional[bool]
  events: list[dict]

# type of an asgi application
ASGIApp = Callable[[dict, Callable[[dict], Awaitable[None]], Callable[[],Awaitable[dict]]], Awaitable[None]]

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
      else: return ["unknown"]

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

class ASGIEventReceiver(Receiver):
  _own_address: int
  _recv_queue: asyncio.Queue[ASGIEventMessage]

  def __init__(self, client: 'Client', own_address: int):
    super().__init__(client)
    self._own_address = own_address

  def on_message(self, message: Message):
    if not isinstance(message, AddressedMessage): return
    a_message: AddressedMessage = message
    if a_message.address != self._own_address: return
    if not isinstance(a_message.data, MessagePackData): return
    try:
      self._recv_queue.put_nowait(ASGIEventMessage.parse_obj(a_message.data.data))
    except: pass

class ASGIEventSender:
  def __init__(self, client: 'Client', remote_address: int, connection_id: str):
    self._client = client
    self._remote_address = remote_address
    self._connection_id = connection_id
  async def send(self, event: dict): await self._send(events=[event])
  async def close(self): await self._send(events=[], closed=True)
  async def _send(self, events: list[dict], closed: Optional[bool] = None):
    events = [MessagePackValueTransformer.annotate_value(event) for event in events]
    await self._client.send_to(self._remote_address, MessagePackData(ASGIEventMessage(connection_id=self._connection_id, events=events, closed=closed).dict()))

class ASGIAppRunner:
  _client: 'Client'
  _app: ASGIApp
  _init_receiver: Receiver
  _own_address: int

  def __init__(self, client: 'Client', app: ASGIApp, init_conn_desc: str, own_address: Optional[int] = None):
    self._client = client
    self._app = app
    
    assert len(client._addresses) > 0, "The client must have at least one address to host an ASGI application"
    if own_address is not None: self._own_address = own_address
    else: self._own_address = client.default_address

    self._init_receiver = FetchRequestReceiver(client, init_conn_desc, self._own_address)

  async def async_start(self, stop_signal: asyncio.Event):
    self._init_receiver.start_recv()
    while not stop_signal.is_set():
      if self._init_receiver.empty(): 
        await asyncio.sleep(0.001)
        continue

      raw_request: FetchRequest = await self._init_receiver.recv()
      init_request = ASGIInitMessage.parse_obj(raw_request.body)

      config = ASGIConnectionConfig(
        scope=JSONValueTransformer.deannotate_value(init_request.scope), 
        connection_id=init_request.connection_id, 
        remote_address=init_request.return_address, 
        own_address=self._own_address)
      
      self._start_connection(config)
      await raw_request.respond(None)
    self._init_receiver.stop_recv()

  def _start_connection(self, config: ASGIConnectionConfig):
    receiver = ASGIEventReceiver(self._client, config.own_address)
    receiver.start_recv()
    sender = ASGIEventSender(self._client, config.remote_address, config.connection_id)
    
    recv_queue = asyncio.Queue()
    
    async def send(event: dict): 
      await sender.send(event)
    async def receive() -> dict: 
      while recv_queue.empty(): 
        data = await receiver.recv()
        for event in data.events: 
          event = MessagePackValueTransformer.deannotate_value(event)
          recv_queue.put_nowait(event)
      await recv_queue.get()

    async def run():
      logging.info(f"ASGI instance ({config.connection_id}) starting!")
      await self._app(config.scope, receive, send)
      await sender.close()
      receiver.stop_recv()
      logging.info(f"ASGI instance ({config.connection_id}) finished!")

    return asyncio.create_task(run())

class ASGIProxyApp:
  _client: 'Client'
  _remote_address: int
  _init_descriptor: str
  _own_address: int

  def __init__(self, client: 'Client', remote_address: int, init_descriptor: str, own_address: Optional[int] = None):
    self._client = client
    self._remote_address = remote_address
    self._init_descriptor = init_descriptor
    assert len(client._addresses) > 0, "The client must have at least one address to host an ASGI application"
    if own_address is not None: self._own_address = own_address
    else: self._own_address = client.default_address
    
  async def __call__(self, scope, receive: Callable[[], Awaitable[dict]], send: Callable[[dict], Awaitable[None]]):
    connection_id = str(uuid4())
    ser_scope = JSONValueTransformer.annotate_value(scope)
    await self._client.fetch(self._remote_address, self._init_descriptor, ASGIInitMessage(connection_id=connection_id, return_address=self._own_address, scope=ser_scope).dict())

    closed_event = asyncio.Event()
    receiver = ASGIEventReceiver(self._client, self._own_address)
    sender = ASGIEventSender(self._client, self._remote_address, connection_id)

    async def recv_loop(): 
      while not closed_event.is_set(): await sender.send(await receive())
    async def send_loop():
      receiver.start_recv()
      while not closed_event.is_set():
        data = await receiver.recv()
        for event in data.events: await send(MessagePackValueTransformer.deannotate_value(event))
        if data.closed: closed_event.set()
      receiver.stop_recv()

    recv_task = asyncio.create_task(recv_loop())
    send_task = asyncio.create_task(send_loop())
    await closed_event.wait()
    recv_task.cancel()
    send_task.cancel()
