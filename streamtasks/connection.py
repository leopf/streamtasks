from abc import ABC, abstractmethod
import asyncio
import json
import logging
import struct
from typing import Awaitable, Callable
from streamtasks.net import ConnectionClosedError, Link
from streamtasks.net.message.serialize import deserialize_message, serialize_message
from streamtasks.net.message.types import Message
from importlib.metadata import version

from streamtasks.worker import Worker

def _get_version_specifier(): return ".".join(version(__name__.split(".", maxsplit=1)[0]).split(".")[:2]) # NOTE: major.minor during alpha

class RawConnection(ABC):
  async def handshake(self, extra_data: dict):
    try:
      data = { **extra_data, "version": _get_version_specifier() }
      await self.send(json.dumps(data).encode("utf-8"))
      other_data = json.loads((await self.recv()).decode("utf-8"))
      if not isinstance(other_data, dict): raise ValueError()
      self.validate_handshake(other_data)
    except:
      await self.close()
      raise
  
  def validate_handshake(self, data: dict):
    if data["version"] != _get_version_specifier(): raise ValueError("Version missmatch!")
  
  @abstractmethod
  async def close(self): pass
  @abstractmethod
  async def send(self, data: bytes): pass
  @abstractmethod
  async def recv(self) -> bytes: pass

class RawStreamConnection(RawConnection):
  SYNC_WORD = b"\xb8\x23\xa0\x6f"
  
  def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    super().__init__()
    self._reader = reader
    self._writer = writer

  async def close(self):
    self._writer.close()
    await self._writer.wait_closed()

  # NOTE: shield against desync 
  async def send(self, data: bytes): await asyncio.shield(self._send(data))
  async def recv(self) -> bytes: await asyncio.shield(self._recv())

  async def _send(self, data: bytes):
    await self._writer.write(RawStreamConnection.SYNC_WORD)
    await self._writer.write(struct.pack("<L", len(data)))
    await self._writer.write(data)
    await self._writer.drain()
    
  async def _recv(self) -> bytes:
    sync_index = 0
    while sync_index < len(RawStreamConnection.SYNC_WORD):
      next_byte = await self._reader.read(1)
      if len(next_byte) == 1 and RawStreamConnection.SYNC_WORD[sync_index] == next_byte[0]: sync_index += 1
      else: sync_index = 0
    data_len_raw = await self._reader.read(4)
    if len(data_len_raw) != 4: raise ValueError("Invalid length for 'data_len'!")
    data_len = struct.unpack("<L", data_len_raw)
    data = await self._reader.read(data_len)
    if len(data) != data_len: raise ValueError("Invalid data length!")
    return data

class RawConnectionLink(Link):
  def __init__(self, connection: RawConnection, cost: int):
    super().__init__(cost)
    self._connection = connection
    
  async def _send(self, message: Message):
    try: await self._connection.send(serialize_message(message))
    except asyncio.CancelledError: raise
    except: raise ConnectionClosedError()

  async def _recv(self) -> Message:
    try: return deserialize_message(await self._connection.recv())
    except asyncio.CancelledError: raise
    except: raise ConnectionClosedError()

class _StreamServerBase(Worker):
  def __init__(self, node_link: Link, cost: int = 100, handshake_data: dict = {}):
    super().__init__(node_link)
    self.cost = cost
    self.handshake_data = handshake_data
    
  async def run(self):
    try:
      await self.setup()
      await self.run_server()
    finally:
      await self.shutdown()
      
  @abstractmethod
  async def run_server(self): pass

  async def on_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
      connection = RawStreamConnection(reader, writer)
      await connection.handshake(self.handshake_data)
      await self.switch.add_link(RawConnectionLink(connection, self.cost))
    except BaseException as e:
      logging.warning(f"Failed to initialize connection. Error: {e}")
      raise e

class TCPSocketServer(_StreamServerBase):
  def __init__(self, node_link: Link, host: str, port: int, cost: int = 100, handshake_data: dict = {}):
    super().__init__(node_link, cost, handshake_data)
    self.host = host
    self.port = port
  
  async def run_server(self):
    server = await asyncio.start_server(self.on_connection, self.host, self.port)
    async with server: await server.serve_forever()

class UnixSocketServer(_StreamServerBase):
  def __init__(self, node_link: Link, path: str, cost: int = 100, handshake_data: dict = {}):
    super().__init__(node_link, cost, handshake_data)
    self.path = path
  
  async def run_server(self):
    server = await asyncio.start_unix_server(self.on_connection, self.path)
    async with server: await server.serve_forever()

async def connect_tcp_socket(host: str, port: int, cost: int, handshake_data: dict = {}):
  rw = await asyncio.open_connection(host, port)
  connection = RawStreamConnection(*rw)
  await connection.handshake(handshake_data)
  return RawConnectionLink(connection, cost) 

async def connect_unix_socket(path: str, cost: int, handshake_data: dict = {}):
  rw = await asyncio.open_unix_connection(path)
  connection = RawStreamConnection(*rw)
  await connection.handshake(handshake_data)
  return RawConnectionLink(connection, cost)

class AutoReconnector(Worker):
  def __init__(self, node_link: Link, connect_fn: Callable[[], Awaitable[Link]], delay: float = 1):
    super().__init__(node_link)
    self.connect_fn = connect_fn
    self.delay = delay
    self.disconnected_event = asyncio.Event()
    
  async def run(self):
    try:
      await self.setup()
      while True:
        try:
          link = await self.connect_fn()
          await self.switch.add_link(link)
          link.on_closed.append(self.disconnected_event.set)
          if link.closed: self.disconnected_event.set() # in case it closed already
          await self.disconnected_event.wait()
          await asyncio.wait(self.delay)
        finally: self.disconnected_event.clear()
    finally: await self.shutdown()