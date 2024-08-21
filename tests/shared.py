import asyncio
from functools import wraps
import os
import unittest
from streamtasks.client import Client
from streamtasks.client.receiver import Receiver
from streamtasks.net.messages import AddressedMessage, Message
from streamtasks.net.serialization import RawData

def async_timeout(seconds):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs): return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
        return wrapper
    return decorator

def full_test(o): return unittest.skipIf(not int(os.getenv("FULL") or "0"), "Disabled for performance reasons. Use env FULL=1 to enable.")(o)

class AddressReceiver(Receiver[tuple[int, RawData]]):
  def __init__(self, client: 'Client', address: int, port: int):
    super().__init__(client)
    self._address = address
    self._port = port

  def on_message(self, message: Message):
    if not isinstance(message, AddressedMessage): return
    a_message: AddressedMessage = message
    if a_message.address == self._address and a_message.port == self._port:
      self._recv_queue.put_nowait((a_message.address, a_message.data))
