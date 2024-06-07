from abc import ABC, abstractmethod
import asyncio
import functools
import json
import logging
import os
import struct
import tempfile
from typing import Awaitable, Callable
from streamtasks.env import NODE_NAME
from streamtasks.net import ConnectionClosedError, Link
from streamtasks.net.serialization import deserialize_message, serialize_message
from streamtasks.net.messages import Message
from importlib.metadata import version
import urllib.parse
from streamtasks.utils import AsyncBool, AsyncTrigger
from streamtasks.worker import Worker

def _get_version_specifier(): return ".".join(version(__name__.split(".", maxsplit=1)[0]).split(".")[:2]) # NOTE: major.minor during alpha

class RawConnection(ABC):
  def __init__(self) -> None:
    super().__init__()
    self._send_lock = asyncio.Lock()
    self._recv_lock = asyncio.Lock()

  async def handshake(self, extra_data: dict):
    try:
      data = { **extra_data, "version": _get_version_specifier() }
      await self.send(json.dumps(data).encode("utf-8"))
      other_data = json.loads((await self.recv()).decode("utf-8"))
      if not isinstance(other_data, dict): raise ValueError()
      self.validate_handshake(other_data)
    except BaseException as e:
      self.close()
      raise e

  def validate_handshake(self, data: dict):
    if data["version"] != _get_version_specifier(): raise ValueError("Version missmatch!")

  @abstractmethod
  def close(self): pass
  async def send(self, data: bytes):
    async with self._send_lock:
      await asyncio.shield(self._send(data))
  async def recv(self):
    async with self._recv_lock:
      return await asyncio.shield(self._recv())

  @abstractmethod
  async def _send(self, data: bytes): pass
  @abstractmethod
  async def _recv(self) -> bytes: pass

class RawStreamConnection(RawConnection):
  SYNC_WORD = b"\xb8\x23\xa0\x6f"

  def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    super().__init__()
    self._reader = reader
    self._writer = writer

  def close(self): self._writer.close()

  async def send(self, data: bytes):
    try: return await super().send(data)
    except (EOFError, ConnectionError, BrokenPipeError) as e:
      raise ConnectionClosedError(str(e))

  async def recv(self):
    try: return await super().recv()
    except (EOFError, ConnectionError, BrokenPipeError, asyncio.IncompleteReadError) as e:
      raise ConnectionClosedError(str(e))

  async def _send(self, data: bytes):
    self._writer.write(RawStreamConnection.SYNC_WORD)
    self._writer.write(struct.pack("<L", len(data)))
    self._writer.write(data)
    await self._writer.drain()

  async def _recv(self) -> bytes:
    sync_index = 0
    while sync_index < len(RawStreamConnection.SYNC_WORD):
      next_byte = await self._reader.readexactly(1)
      if RawStreamConnection.SYNC_WORD[sync_index] == next_byte[0]: sync_index += 1
      else: sync_index = 0
    data_len, = struct.unpack("<L", await self._reader.readexactly(4))
    return await self._reader.readexactly(data_len)

class RawConnectionLink(Link):
  def __init__(self, connection: RawConnection, cost: int):
    super().__init__(cost)
    self._connection = connection
    self.on_closed.append(connection.close)

  async def _send(self, message: Message):
    try: await self._connection.send(serialize_message(message))
    except asyncio.CancelledError: raise
    except BaseException as e: raise ConnectionClosedError(origin=e)

  async def _recv(self) -> Message:
    try: return deserialize_message(await self._connection.recv())
    except asyncio.CancelledError: raise
    except: raise ConnectionClosedError()

class ServerBase(Worker):
  def __init__(self, link: Link, cost: int, handshake_data: dict = {}):
    super().__init__(link)
    self.cost = cost
    self.handshake_data = handshake_data
    self._running_event = asyncio.Event()
    self._connection_count_trigger = AsyncTrigger()
    self._connection_count = 0

  @property
  def running(self): return self._running_event.is_set()

  @property
  def connection_count(self): return self._connection_count

  async def run(self):
    try:
      await self.setup()
      self._running_event.set()
      await self.run_server()
    finally:
      self._running_event.clear()
      await self.shutdown()

  @abstractmethod
  async def run_server(self): pass

  async def wait_running(self): await self._running_event.wait()
  async def wait_connections_changed(self): await self._connection_count_trigger.wait()

  def on_connected(self):
    self._connection_count += 1
    self._connection_count_trigger.trigger()
  def on_disconnected(self):
    self._connection_count -= 1
    self._connection_count_trigger.trigger()

class StreamServerBase(ServerBase):
  async def on_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
      connection = RawStreamConnection(reader, writer)
      await connection.handshake(self.handshake_data)
      link = RawConnectionLink(connection, self.cost)
      await self.switch.add_link(link)
      self.on_connected()
      link.on_closed.append(self.on_disconnected)
    except BaseException as e: logging.warning(f"Failed to initialize connection. Error: {e}")

class DEFAULT_COSTS:
  TCP = 100
  UNIX = 50
  NODE = 25

class TCPSocketServer(StreamServerBase):
  def __init__(self, link: Link, host: str, port: int, cost: int = DEFAULT_COSTS.TCP, handshake_data: dict = {}):
    super().__init__(link, cost, handshake_data)
    self.host = host
    self.port = port

  async def run_server(self):
    server = await asyncio.start_server(self.on_connection, self.host, self.port)
    async with server: await server.serve_forever()

class UnixSocketServer(StreamServerBase):
  def __init__(self, link: Link, path: str, cost: int = DEFAULT_COSTS.UNIX, handshake_data: dict = {}):
    super().__init__(link, cost, handshake_data)
    self.path = path

  async def run_server(self):
    server = await asyncio.start_unix_server(self.on_connection, self.path)
    async with server: await server.serve_forever()

def get_node_socket_path(node_name: str | None):
  if node_name is None: node_name = NODE_NAME()
  return os.path.join(tempfile.gettempdir(), f"{__name__.split('.')[0]}-{node_name}.sock")

class NodeServer(UnixSocketServer):
  def __init__(self, link: Link, node_name: str | None = None):
    super().__init__(link, get_node_socket_path(node_name), DEFAULT_COSTS.NODE)

async def connect_tcp_socket(host: str, port: int, cost: int = DEFAULT_COSTS.TCP, handshake_data: dict = {}):
  rw = await asyncio.open_connection(host, port)
  connection = RawStreamConnection(*rw)
  await connection.handshake(handshake_data)
  return RawConnectionLink(connection, cost)

async def connect_unix_socket(path: str, cost: int = DEFAULT_COSTS.UNIX, handshake_data: dict = {}):
  rw = await asyncio.open_unix_connection(path)
  connection = RawStreamConnection(*rw)
  await connection.handshake(handshake_data)
  return RawConnectionLink(connection, cost)

async def connect_node(node_name: str | None = None, handshake_data: dict = {}): return await connect_unix_socket(get_node_socket_path(node_name), DEFAULT_COSTS.NODE, handshake_data)

def _extract_cost_from_query_dict(query_params: dict[str, list[str]]):
  if "cost" in query_params and len(query_params["cost"]) == 1 and query_params["cost"][0].isdigit(): return int(query_params.pop("cost")[0])
  return None

async def connect(url: str | None = None):
  handshake_data = {}
  cost: int | None = None
  if url is None: return await connect_node(handshake_data=handshake_data)

  purl = urllib.parse.urlparse(url)
  handshake_data = { **handshake_data }
  if purl.username is not None: handshake_data["username"] = purl.username
  if purl.password is not None: handshake_data["password"] = purl.password
  if purl.query is not None:
    qs_data = urllib.parse.parse_qs(purl.query)
    cost = _extract_cost_from_query_dict(qs_data) or cost
    handshake_data.update({ k: v[0] for k, v in qs_data.items() if len(v) == 1 })

  if purl.scheme == "unix":
    if purl.path is None: raise ValueError("Socket path must not be none!")
    return await connect_unix_socket(purl.path, cost=cost or DEFAULT_COSTS.UNIX, handshake_data=handshake_data)
  elif purl.scheme == "tcp":
    if purl.port is None: raise ValueError("Port must not be none!")
    if purl.hostname is None: raise ValueError("Hostname must not be none!")
    return await connect_tcp_socket(purl.hostname, purl.port, cost=cost or DEFAULT_COSTS.TCP, handshake_data=handshake_data)
  else: return await connect_node(url, handshake_data)

def get_server(link: Link, url: str | None = None) -> ServerBase:
  handshake_data = {}
  cost: int | None = None
  if url is None: return NodeServer(link)
  purl = urllib.parse.urlparse(url)

  if purl.query is not None:
    qs_data = urllib.parse.parse_qs(purl.query)
    cost = _extract_cost_from_query_dict(qs_data) or cost
    handshake_data.update({ k: v[0] for k, v in qs_data.items() if len(v) == 1 })

  if purl.scheme == "unix":
    if purl.path is None: raise ValueError("Socket path must not be none!")
    return UnixSocketServer(link, purl.path, cost=cost or DEFAULT_COSTS.UNIX, handshake_data=handshake_data)
  elif purl.scheme == "tcp":
    if purl.port is None: raise ValueError("Port must not be none!")
    if purl.hostname is None: raise ValueError("Hostname must not be none!")
    return TCPSocketServer(link, purl.hostname, purl.port, cost=cost or DEFAULT_COSTS.TCP, handshake_data=handshake_data)
  else: return NodeServer(link, url)

class AutoReconnector(Worker):
  def __init__(self, link: Link, connect_fn: Callable[[], Awaitable[Link]], delay: float = 1):
    super().__init__(link)
    self.connect_fn = connect_fn
    self.delay = delay
    self._async_connected = AsyncBool()

  @property
  def connected(self): return self._async_connected.value

  async def run(self):
    try:
      await self.setup()
      while True:
        try:
          link = await self.connect_fn()
          await self.switch.add_link(link)
          self._async_connected.set(True)
          link.on_closed.append(functools.partial(self._async_connected.set, False))
          if link.closed: self._async_connected.set(False) # in case it closed already
          await self._async_connected.wait(False)
          await asyncio.wait(self.delay)
          logging.info("reconnecting")
        except (ConnectionClosedError, ConnectionError): pass
    finally: await self.shutdown()

  async def wait_connected(self, connected: bool = True): await self._async_connected.wait(connected)
