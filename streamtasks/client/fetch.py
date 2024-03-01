from streamtasks.client.receiver import Receiver
from streamtasks.net import Endpoint
from streamtasks.net.message.types import AddressedMessage, Message
from streamtasks.net.message.data import MessagePackData
import asyncio
from pydantic import BaseModel, ValidationError
from typing import TYPE_CHECKING, Any, Optional, Callable, Awaitable
import logging

from streamtasks.services.protocols import WorkerPorts
if TYPE_CHECKING:
  from streamtasks.client import Client


class FetchRequestMessage(BaseModel):
  return_address: int
  return_port: int
  descriptor: str
  body: Any


class FetchResponseMessage(BaseModel):
  body: Any


class FetchRequest:
  def __init__(self, client: 'Client', return_endpoint: Endpoint, body: Any):
    self._client = client
    self._return_endpoint = return_endpoint
    self.body = body
    self.response_sent = False

  async def respond(self, body: Any):
    await self._client.send_to(self._return_endpoint, MessagePackData(FetchResponseMessage(body=body).model_dump()))
    self.response_sent = True


class FetchReponseReceiver(Receiver):
  def __init__(self, client: 'Client', return_port: int):
    super().__init__(client)
    self._recv_queue: asyncio.Queue[Any]
    self._return_port = return_port

  def on_message(self, message: Message):
    if not isinstance(message, AddressedMessage): return
    a_message: AddressedMessage = message
    if not a_message.port == self._return_port or not isinstance(a_message.data, MessagePackData): return
    try:
      fr_message = FetchResponseMessage.model_validate(a_message.data.data)
      self._recv_queue.put_nowait(fr_message.body)
    except ValidationError: pass


class FetchServer(Receiver):
  def __init__(self, client: 'Client', port: int = WorkerPorts.FETCH):
    super().__init__(client)
    self._recv_queue: asyncio.Queue[tuple[str, FetchRequest]]
    self._descriptor_mapping: dict[str, Callable[[FetchRequest], Awaitable[Any]]] = {}
    self._port: dict[str, Callable[[FetchRequest], Awaitable[Any]]] = port

  def add_route(self, descriptor: str, func: Callable[[FetchRequest], Awaitable[Any]]): self._descriptor_mapping[descriptor] = func
  def remove_route(self, descriptor: str): self._descriptor_mapping.pop(descriptor, None)

  def route(self, descriptor: str):
    def decorator(func):
      self._descriptor_mapping[descriptor] = func
      return func
    return decorator

  def on_message(self, message: Message):
    if not isinstance(message, AddressedMessage): return
    a_message: AddressedMessage = message
    if a_message.port != self._port or not isinstance(a_message.data, MessagePackData): return
    try:
      fr_message = FetchRequestMessage.model_validate(a_message.data.data)
      if fr_message.descriptor in self._descriptor_mapping:
        self._recv_queue.put_nowait((fr_message.descriptor, FetchRequest(self._client, (fr_message.return_address, fr_message.return_port), fr_message.body)))
    except ValidationError: pass

  async def start(self):
    async with self:
      while True:
        descriptor, fr = await self.get()
        if descriptor in self._descriptor_mapping:
          try:
            await self._descriptor_mapping[descriptor](fr)
            if not fr.response_sent: await fr.respond(None)
          except Exception as e: logging.debug(e, fr, descriptor)


class FetchRequestReceiver(Receiver):
  def __init__(self, client: 'Client', descriptor: str, address: Optional[int] = None, port: int = WorkerPorts.FETCH):
    super().__init__(client)
    self._recv_queue: asyncio.Queue[FetchRequest]
    self._descriptor = descriptor
    self._address = address
    self._port = port

  def on_message(self, message: Message):
    if not isinstance(message, AddressedMessage): return
    a_message: AddressedMessage = message
    if (self._address is not None and a_message.address != self._address) or \
      a_message.port != self._port or not isinstance(a_message.data, MessagePackData): return
    try:
      fr_message = FetchRequestMessage.model_validate(a_message.data.data)
      if fr_message.descriptor == self._descriptor:
        self._recv_queue.put_nowait(FetchRequest(self._client, (fr_message.return_address, fr_message.return_port), fr_message.body))
    except ValidationError: pass