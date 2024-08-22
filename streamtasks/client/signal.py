import asyncio
import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable
from pydantic import BaseModel, ValidationError
from streamtasks.client.receiver import Receiver
from streamtasks.net import EndpointOrAddress, endpoint_or_address_to_endpoint
from streamtasks.net.serialization import RawData
from streamtasks.net.messages import AddressedMessage, Message
from streamtasks.services.protocols import NetworkPorts

if TYPE_CHECKING:
  from streamtasks.client import Client

class SignalMessage(BaseModel):
  descriptor: str
  body: Any


class SignalServer(Receiver[tuple[str, Any]]):
  def __init__(self, client: 'Client', port: int = NetworkPorts.SIGNAL):
    super().__init__(client)
    self._descriptor_mapping: dict[str, Callable[[Any], Awaitable[Any]]] = {}
    self._port = port

  def add_route(self, descriptor: str, func: Callable[[Any], Awaitable[Any]]): self._descriptor_mapping[descriptor] = func
  def remove_route(self, descriptor: str): self._descriptor_mapping.pop(descriptor, None)

  def route(self, descriptor: str):
    def decorator(func):
      self._descriptor_mapping[descriptor] = func
      return func
    return decorator

  def on_message(self, message: Message):
    if not isinstance(message, AddressedMessage): return
    a_message: AddressedMessage = message
    if a_message.port != self._port or not isinstance(a_message.data, RawData): return
    try:
      s_message = SignalMessage.model_validate(a_message.data.data)
      if s_message.descriptor in self._descriptor_mapping:
        self._recv_queue.put_nowait((s_message.descriptor, s_message.body))
    except ValidationError: pass

  async def run(self):
    async with self:
      while True:
        req_message: tuple[str, Any] = await self.get()
        descriptor, data = req_message
        if descriptor in self._descriptor_mapping:
          try: await self._descriptor_mapping[descriptor](data)
          except asyncio.CancelledError: raise
          except BaseException as e: logging.debug(e, descriptor)

async def send_signal(client: 'Client', endpoint: EndpointOrAddress, descriptor: str, body: Any):
  await client.send_to(endpoint_or_address_to_endpoint(endpoint, NetworkPorts.SIGNAL), RawData(SignalMessage(descriptor=descriptor, body=body).model_dump()))
