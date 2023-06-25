from streamtasks.client.receiver import Receiver
from streamtasks.comm.types import AddressedMessage, Message
from streamtasks.comm.serialization import JsonData
import asyncio
from pydantic import BaseModel
from typing import TYPE_CHECKING, Any, Optional
if TYPE_CHECKING:
    from streamtasks.client import Client

class FetchRequestMessage(BaseModel):
  return_address: int
  request_id: int
  descriptor: str
  body: Any

class FetchResponseMessage(BaseModel):
  request_id: int
  body: Any

class FetchRequest:
  body: Any
  _client: 'Client'
  _return_address: int
  _request_id: int

  def __init__(self, client: 'Client', return_address: int, request_id: int, body: Any):
    self._client = client
    self._return_address = return_address
    self._request_id = request_id
    self.body = body

  async def respond(self, body: Any):
    await self._client.send_to(self._return_address, JsonData(FetchResponseMessage(request_id=self._request_id, body=body).dict()))

class FetchReponseReceiver(Receiver):
  _fetch_id: int
  _recv_queue: asyncio.Queue[Any]

  def __init__(self, client: 'Client', fetch_id: int):
    super().__init__(client)
    self._fetch_id = fetch_id

  def on_message(self, message: Message):
    if isinstance(message, AddressedMessage):
      a_message: AddressedMessage = message
      if isinstance(a_message.data, JsonData):
        try:
          fr_message = FetchResponseMessage.parse_obj(a_message.data.data)
          if fr_message.request_id == self._fetch_id:
            self._recv_queue.put_nowait(fr_message.body)
        except: pass


class FetchRequestReceiver(Receiver):
  _descriptor: str
  _recv_queue: asyncio.Queue[FetchRequest]
  _receive_address: Optional[int]

  def __init__(self, client: 'Client', descriptor: str, receive_address: Optional[int] = None):
    super().__init__(client)
    self._descriptor = descriptor
    self._receive_address = receive_address

  def on_message(self, message: Message):
    if not isinstance(message, AddressedMessage): return
    a_message: AddressedMessage = message
    if self._receive_address is not None and a_message.address != self._receive_address: return
    if not isinstance(a_message.data, JsonData): return
    try:
      fr_message = FetchRequestMessage.parse_obj(a_message.data.data)
      if fr_message.descriptor == self._descriptor:
        self._recv_queue.put_nowait(FetchRequest(self._client, fr_message.return_address, fr_message.request_id, fr_message.body))
    except: pass