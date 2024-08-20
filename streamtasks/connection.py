from abc import ABC, abstractmethod
from dataclasses import dataclass
import asyncio
import functools
import logging
import os
import platform
import struct
import tempfile
import websockets
import websockets.connection
from streamtasks.env import NODE_NAME
from typing import Any, Awaitable, Callable
from streamtasks.error import PlatformNotSupportedError
from streamtasks.net import ConnectionClosedError, Link
from streamtasks.net.serialization import deserialize_message, serialize_message
from streamtasks.net.messages import Message
from importlib.metadata import version
import urllib.parse
from streamtasks.utils import AsyncBool, AsyncTrigger
from streamtasks.worker import Worker
import msgpack

class DEFAULT_COSTS:
  WEBSOCKET = 150
  TCP = 100
  UNIX = 50
  NODE = 25

def _get_version_specifier(): return ".".join(version(__name__.split(".", maxsplit=1)[0]).split(".")[:2]) # NOTE: major.minor during alpha

@dataclass
class ConnectionData:
  cost: int
  handshake_data: dict[str, Any]

@dataclass
class UnixConnectionData(ConnectionData):
  path: str

@dataclass
class NetworkConnectionData(ConnectionData):
  hostname: str
  port: int

class TCPConnectionData(NetworkConnectionData): pass

@dataclass
class WebsocketConnectionData(NetworkConnectionData):
  secure: bool

  @property
  def uri(self):
    scheme = "wss" if self.secure else "ws"
    return f"{scheme}://{self.hostname}:{self.port}"

class AutoReconnector(Worker):
  def __init__(self, connect_fn: Callable[[], Awaitable[Link]], delay: float = 1):
    super().__init__()
    self.connect_fn = connect_fn
    self.delay = delay
    self._async_connected = AsyncBool()

  @property
  def connected(self): return self._async_connected.value

  async def run(self):
    try:
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

class RawConnection(ABC):
  def __init__(self) -> None:
    super().__init__()
    self._send_lock = asyncio.Lock()
    self._recv_lock = asyncio.Lock()

  async def init_client(self, extra_data: dict):
    try:
      client_data = { **extra_data, "version": _get_version_specifier() }
      await self.send(msgpack.packb(client_data))
      server_data = msgpack.unpackb(await self.recv())
      if not isinstance(server_data, dict): raise ValueError()
      if server_data.get("version", None) != _get_version_specifier(): raise ConnectionError("Server version mismatch")
      if server_data.get("accepted", False) != True: raise ConnectionError("Server rejected connection")
    except BaseException as e:
      self.close()
      raise e

  async def init_server(self, extra_data: dict) -> dict:
    try:
      client_data = msgpack.unpackb(await self.recv())
      if not isinstance(client_data, dict): raise ValueError()
      server_auth = extra_data.pop("auth", None)
      client_auth = client_data.get("auth", None)
      accepted = client_data.get("version", None) == _get_version_specifier() and client_auth == server_auth
      server_data = { **extra_data, "accepted": accepted, "version": _get_version_specifier() }
      await self.send(msgpack.packb(server_data))
      if not accepted: raise ConnectionError("Server rejected connection")
    except BaseException as e:
      self.close()
      raise e

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
    except BaseException as e: raise ConnectionClosedError(origin=e)

class ServerBase(Worker):
  def __init__(self, cost: int, handshake_data: dict):
    super().__init__()
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
      await connection.init_server(self.handshake_data)
      link = RawConnectionLink(connection, self.cost)
      await self.switch.add_link(link)
      self.on_connected()
      link.on_closed.append(self.on_disconnected)
    except BaseException as e: logging.warning(f"Failed to initialize connection. Error: {e}")

class RawWebsocketConnection(RawConnection):
  def __init__(self, socket: websockets.WebSocketCommonProtocol) -> None:
    super().__init__()
    self.socket = socket

  async def send(self, data: bytes):
    try: return await super().send(data)
    except websockets.ConnectionClosed as e: raise ConnectionClosedError(origin=e)

  async def recv(self):
    try: return await super().recv()
    except websockets.ConnectionClosed as e: raise ConnectionClosedError(origin=e)

  async def _send(self, data: bytes): await self.socket.send(data)
  async def _recv(self) -> bytes:
    data = None
    while not isinstance(data, bytes): data = await self.socket.recv()
    return data

  def close(self): asyncio.create_task(self.socket.close())

class WebsocketServer(ServerBase):
  def __init__(self, host: str, port: int, cost: int, handshake_data: dict):
    super().__init__(cost, handshake_data)
    self.host = host
    self.port = port

  async def on_connection(self, socket: websockets.WebSocketCommonProtocol):
    try:
      close_event = asyncio.Event()
      connection = RawWebsocketConnection(socket)
      await connection.init_server(self.handshake_data)
      link = RawConnectionLink(connection, self.cost)
      await self.switch.add_link(link)
      self.on_connected()
      link.on_closed.append(self.on_disconnected)
      link.on_closed.append(close_event.set)
      await close_event.wait()
    except BaseException as e: logging.warning(f"Failed to initialize connection. Error: {e}")

  async def run_server(self):
    async with websockets.serve(self.on_connection, host=self.host, port=self.port):
      return await asyncio.Future()

class TCPSocketServer(StreamServerBase):
  def __init__(self, host: str, port: int, cost: int, handshake_data: dict):
    super().__init__(cost, handshake_data)
    self.host = host
    self.port = port

  async def run_server(self):
    server = await asyncio.start_server(self.on_connection, self.host, self.port)
    async with server: await server.serve_forever()

class UnixSocketServer(StreamServerBase):
  def __init__(self, path: str, cost: int, handshake_data: dict):
    if platform.system() == "Windows": raise PlatformNotSupportedError("Windows not supported!")
    super().__init__(cost, handshake_data)
    self.path = path

  async def run_server(self):
    server = await asyncio.start_unix_server(self.on_connection, self.path)
    async with server: await server.serve_forever()

def get_node_socket_path(node_name: str | None):
  if node_name is None: node_name = NODE_NAME()
  return os.path.join(tempfile.gettempdir(), f"{__name__.split('.')[0]}-{node_name}.sock")

def extract_connection_data_from_url(url: str | None):
  if url is None: return UnixConnectionData(path=get_node_socket_path(None), cost=DEFAULT_COSTS.NODE, handshake_data={})

  handshake_data = {}
  cost: int | None = None
  purl = urllib.parse.urlparse(url)
  if purl.username is not None: handshake_data["username"] = purl.username
  if purl.password is not None: handshake_data["password"] = purl.password
  if purl.query is not None:
    qs_data = urllib.parse.parse_qs(purl.query)
    handshake_data.update({ k: v[0] for k, v in qs_data.items() if len(v) == 1 })
    if "cost" in qs_data and len(qs_data["cost"]) == 1 and qs_data["cost"][0].isdigit(): cost = int(qs_data.pop("cost")[0])

  match purl.scheme:
    case "": return UnixConnectionData(path=get_node_socket_path(url), cost=DEFAULT_COSTS.NODE, handshake_data={})
    case "node": return UnixConnectionData(path=get_node_socket_path(purl.hostname or None), cost=cost or DEFAULT_COSTS.NODE, handshake_data=handshake_data)
    case "unix": return UnixConnectionData(path=purl.path, cost=cost or DEFAULT_COSTS.UNIX, handshake_data=handshake_data)
    case "tcp": return TCPConnectionData(hostname=purl.hostname, port=purl.port, cost=cost or DEFAULT_COSTS.TCP, handshake_data=handshake_data)
    case "ws": return WebsocketConnectionData(hostname=purl.hostname, port=purl.port, cost=cost or DEFAULT_COSTS.WEBSOCKET, handshake_data=handshake_data, secure=False)
    case "wss": return WebsocketConnectionData(hostname=purl.hostname, port=purl.port, cost=cost or DEFAULT_COSTS.WEBSOCKET, handshake_data=handshake_data, secure=True)
    case _: raise ValueError("Invalid url scheme!")

async def connect(url: str | None = None):
  data = extract_connection_data_from_url(url)
  connection: RawConnection
  if isinstance(data, UnixConnectionData):
    rw = await asyncio.open_unix_connection(data.path)
    connection = RawStreamConnection(*rw)
  elif isinstance(data, TCPConnectionData):
    rw = await asyncio.open_connection(data.hostname, data.port)
    connection = RawStreamConnection(*rw)
  elif isinstance(data, WebsocketConnectionData):
    socket = await websockets.connect(data.uri)
    connection = RawWebsocketConnection(socket)
  else: raise ValueError("Invalid connection data/url!")
  await connection.init_client(data.handshake_data)
  return RawConnectionLink(connection, data.cost)

def create_server(url: str | None = None) -> ServerBase:
  data = extract_connection_data_from_url(url)
  if isinstance(data, UnixConnectionData):
    return UnixSocketServer(data.path, data.cost, data.handshake_data)
  elif isinstance(data, TCPConnectionData):
    return TCPSocketServer(data.hostname, data.port, cost=data.cost, handshake_data=data.handshake_data)
  elif isinstance(data, WebsocketConnectionData):
    return WebsocketServer(data.hostname, data.port, data.cost, data.handshake_data)
