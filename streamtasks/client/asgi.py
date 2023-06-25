from streamtasks.client.receiver import Receiver
from streamtasks.client.fetch import FetchRequestReceiver, FetchRequest
from streamtasks.comm.types import AddressedMessage, Message
from pydantic import BaseModel
from abc import ABC
from dataclasses import dataclass
import asyncio
import logging
from uuid import uuid4

from typing import TYPE_CHECKING, Any, Awaitable, Optional, Callable
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
    if not isinstance(a_message.data, JsonData): return
    try:
      self._recv_queue.put_nowait(ASGIEventMessage.parse_obj(a_message.data.data))
    except: pass

class ASGIHostServer:
  _client: 'Client'
  _app: ASGIApp
  _init_receiver: Receiver
  _own_address: int

  def __init__(self, client: 'Client', app: ASGIApp, init_conn_desc: str, own_address: Optional[int] = None):
    self._client = client
    self._app = app
    if own_address is not None: self._own_address = own_address
    else: 
      assert len(client._addresses) > 0, "The client must have at least one address to host an ASGI application"
      self._own_address = next(iter(client._addresses))
    self._init_receiver = FetchRequestReceiver(client, init_conn_desc, self._own_address)

  async def start(self, stop_signal: asyncio.Event):
    while not stop_signal.is_set():
      if self._init_receiver.empty(): 
        await asyncio.sleep(0.001)
        continue

      raw_request: FetchRequest = await self._init_receiver.recv()
      init_request = ASGIInitMessage.parse_obj(raw_request.body)

      config = ASGIConnectionConfig(
        scope=init_request.scope, 
        connection_id=init_request.connection_id, 
        remote_address=init_request.return_address, 
        own_address=self._own_address)
      
      self.start_connection(config)
      await raw_request.respond(None)

  def start_connection(self, config: ASGIConnectionConfig):
    receiver = ASGIEventReceiver(self._client, config.own_address)
    receiver.start_recv()
    recv_queue = asyncio.Queue()

    async def send(event: dict):
      await self._client.send_to(config.remote_address, JsonData(ASGIEventMessage(
        connection_id=config.connection_id, 
        event=[event]).dict()
      ))
    async def receive() -> dict: 
      while recv_queue.empty(): 
        data = await receiver.recv()
        for event in data.events: recv_queue.put_nowait(event)
      await recv_queue.get()

    async def run():
      logging.info(f"ASGI instance ({config.connection_id}) starting!")
      await self._app(config.scope, send, receive)
      receiver.stop_recv()
      await self._client.send_to(config.remote_address, JsonData(ASGIEventMessage(
        connection_id=config.connection_id, 
        event=[],
        closed=True).dict()
      ))
      logging.info(f"ASGI instance ({config.connection_id}) finished!")

    return asyncio.create_task(run())

  def __enter__(self):
    self._init_receiver.start_recv()
    return self

  def __exit__(self, *args):
    self._init_receiver.stop_recv()
    return False

class ASGIClientApp:
  _client: 'Client'
  _remote_address: int
  _init_descriptor: str
  _own_address: int

  def __init__(self, client: 'Client', remote_address: int, init_descriptor: str = "asgi.init", own_address: Optional[int] = None):
    self._client = client
    self._remote_address = remote_address
    self._init_descriptor = init_descriptor
    if own_address is not None: self._own_address = own_address
    else: 
      assert len(client._addresses) > 0, "The client must have at least one address to host an ASGI application"
      self._own_address = next(iter(client._addresses))

  def __call__(self, scope, send: Callable[[dict],Awaitable[None]], receive: Callable[[], Awaitable[dict]]):
    connection_id = str(uuid4())
    await self._client.fetch(self._remote_address, self._init_descriptor, ASGIInitMessage(
      connection_id=connection_id,
      return_address=self._own_address,
      scope=scope).dict())

    closed_event = asyncio.Event()

    receiver = ASGIEventReceiver(self._client, self._own_address)

    async def recv_loop():
      while True:
        event = await receive()
        self._client.send_to(self._remote_address, JsonData(ASGIEventMessage(
          connection_id=connection_id,
          event=[event]).dict()
        ))
    
    async def send_loop():
      while True:
        data = await receiver.recv()
        if data.closed:
          closed_event.set()
          break
        for event in data.events:
          await send(event)

    recv_task = asyncio.create_task(recv_loop())
    send_task = asyncio.create_task(send_loop())
    await closed_event.wait()
    recv_task.cancel()
    send_task.cancel()
