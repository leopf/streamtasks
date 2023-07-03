from streamtasks.comm.types import *
from streamtasks.comm.helpers import *
from streamtasks.comm.serialize import serialize_message, deserialize_message
from streamtasks.helpers import IdTracker

from typing import Union, Optional, Any, Iterable
import multiprocessing.connection as mpconn
from abc import ABC, abstractmethod, abstractstaticmethod
from dataclasses import dataclass
from typing_extensions import Self
import logging
import os
import asyncio

RemoteAddress = Union[str, tuple[str, int]]

class Connection(ABC):
  in_topics: set[int]
  addresses: dict[int, int]
  out_topics: dict[int, int]
  recv_topics: set[int]
  cost: int

  closed: asyncio.Event
  ignore_internal: bool

  def __init__(self, cost: int = 1):
    self.in_topics = set()
    self.out_topics = dict()
    self.addresses = dict()
    self.recv_topics = set()

    self.closed = asyncio.Event()

    assert cost > 0, "Cost must be greater than 0"
    self.cost = cost

  def __del__(self): self.close()
  def close(self): self.closed.set()

  def get_priced_out_topics(self, topics: set[int] = None) -> set[PricedId]:
    if topics is None:
      return set(PricedId(topic, cost) for topic, cost in self.out_topics.items())
    else:
      return set(PricedId(topic, self.out_topics[topic]) for topic in topics if topic in self.out_topics)

  def get_priced_addresses(self, addresses: set[int] = None) -> set[PricedId]:
    if addresses is None:
      return set(PricedId(address, cost) for address, cost in self.addresses.items())
    else:
      return set(PricedId(address, self.addresses[address]) for address in addresses if address in self.addresses)

  async def send(self, message: Message):
    if isinstance(message, InTopicsChangedMessage):
      itc_message: InTopicsChangedMessage = message
      self.recv_topics = self.recv_topics.union(itc_message.add).difference(itc_message.remove)
    elif isinstance(message, OutTopicsChangedMessage):
      otc_message: OutTopicsChangedMessage = message
      message = OutTopicsChangedMessage(set(PricedId(pt.id, pt.cost + self.cost) for pt in otc_message.add), otc_message.remove)
    elif isinstance(message, AddressesChangedMessage):
      ac_message: AddressesChangedMessage = message
      message = AddressesChangedMessage(set(PricedId(pa.id, pa.cost + self.cost) for pa in ac_message.add), ac_message.remove)
    await self._send(message)

  async def recv(self) -> Message:
    message = None
    while message is None:
      message = await self._recv_one()
      message = self._process_recv_message(message)

    return message

  async def _recv_one(self):
    tasks = [
      asyncio.create_task(self.closed.wait()),
      asyncio.create_task(self._recv())
    ]
    try:
      done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

      results = [ task.result() for task in done ]
      assert len(results) > 0, "Invalid state"
      if len(results) > 1 or results[0] == True: 
        raise Exception("Connection closed")
      return results[0]
    finally:
      for task in tasks: task.cancel()

  @abstractmethod
  async def _send(self, message: Message):
    pass

  @abstractmethod
  async def _recv(self) -> Message:
    pass

  def _process_recv_message(self, message: Message) -> Message:
    if isinstance(message, InTopicsChangedMessage):
      itc_message: InTopicsChangedMessage = message
      message = InTopicsChangedMessage(itc_message.add.difference(self.in_topics), itc_message.remove.intersection(self.in_topics))
      self.in_topics = self.in_topics.union(message.add).difference(message.remove)
      
      if len(message.add) == 0 and len(message.remove) == 0:
        return None

    elif isinstance(message, OutTopicsChangedMessage):
      otc_message: OutTopicsChangedMessage = message
      message = OutTopicsChangedRecvMessage(
        set(PricedId(pt.id, pt.cost + self.cost) for pt in otc_message.add), 
        set(PricedId(t, self.out_topics[t]) for t in otc_message.remove if t in self.out_topics))
      for address in otc_message.remove: self.out_topics.pop(address, None)
      for pt in message.add: self.out_topics[pt.id] = pt.cost

    elif isinstance(message, AddressesChangedMessage):
      ac_message: AddressesChangedMessage = message
      message = AddressesChangedRecvMessage(
        set(PricedId(pa.id, pa.cost + self.cost) for pa in ac_message.add), 
        set(PricedId(a, self.addresses[a]) for a in ac_message.remove if a in self.addresses))
      for address in ac_message.remove: self.addresses.pop(address, None)
      for pa in message.add: self.addresses[pa.id] = pa.cost

    return message

class IPCConnection(Connection):
  connection: mpconn.Connection

  def __init__(self, connection: mpconn.Connection, cost: Optional[int] = None):
    super().__init__(cost)
    self.connection = connection

  def close(self):
    super().close()
    self.connection.close()

  async def _send(self, message: Message):
    self.validate_open()
    await asyncio.sleep(0)
    self.connection.send(message)

  async def _recv(self) -> Optional[Message]:
    self.validate_open()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self.connection.recv) # TODO: better ipc and using custom serializer + asyncio

  def validate_open(self):
    if self.connection.closed:
      if not self.closed.is_set(): self.close()
      raise Exception("Connection closed")

class QueueConnection(Connection):
  out_messages: asyncio.Queue[Message]
  in_messages: asyncio.Queue[Message]
  close_signal: asyncio.Event

  def __init__(self, close_signal: asyncio.Event, out_messages: asyncio.Queue, in_messages: asyncio.Queue):
    super().__init__()
    self.out_messages = out_messages
    self.in_messages = in_messages
    self.close_signal = close_signal

  def close(self):
    super().close()
    if not self.close_signal.is_set(): self.close_signal.set()

  async def _send(self, message: Message):
    self.validate_open()
    await self.out_messages.put(message)

  async def _recv(self) -> Message:
    self.validate_open()
    return await self.in_messages.get()

  def validate_open(self):
    if self.close_signal.is_set():
      if not self.closed.is_set(): self.close()
      raise Exception("Connection closed")

class RawQueueConnection(QueueConnection):
  out_messages: asyncio.Queue[bytes]
  in_messages: asyncio.Queue[bytes]

  async def _send(self, message: Message):
    self.validate_open()
    await self.out_messages.put(serialize_message(message))

  async def _recv(self) -> Message:
    self.validate_open()
    return deserialize_message(await self.in_messages.get())

def create_local_cross_connector(raw: bool = False) -> tuple[Connection, Connection]:
  close_signal = asyncio.Event()
  messages_a, messages_b = asyncio.Queue(), asyncio.Queue()
  if raw:
    return RawQueueConnection(close_signal, messages_a, messages_b), RawQueueConnection(close_signal, messages_b, messages_a)
  else:
    return QueueConnection(close_signal, messages_a, messages_b), QueueConnection(close_signal, messages_b, messages_a)

def connect_to_listener(address: RemoteAddress) -> Optional[IPCConnection]:
  logging.info(f"Connecting to {address}")
  try:
    conn = IPCConnection(mpconn.Client(address))
    logging.info(f"Connected to {address}")
    return conn
  except BaseException:
    logging.error(f"Connection to {address} refused, Error: {traceback.format_exc()}")
    return None

def get_node_socket_path(id: int) -> str:
  if os.name == 'nt':
      return f'\\\\.\\pipe\\streamtasks-{id}'
  else:
      return f'/tmp/streamtasks-{id}.sock'

class Switch:
  in_topics: IdTracker
  out_topics: PricedIdTracker
  addresses: PricedIdTracker

  stream_controls: dict[int, TopicControlData]
  connections: list[Connection]
  pending_connections: list[Connection]
  connection_receiving_tasks: dict[Connection, asyncio.Task]
  connections_pending: asyncio.Event

  def __init__(self):
    self.connections = []
    self.pending_connections = []
    self.connection_receiving_tasks = {}
    self.connections_pending = asyncio.Event()

    self.in_topics = IdTracker()
    self.out_topics = PricedIdTracker()
    self.addresses = PricedIdTracker()
    self.stream_controls = {}

  async def add_connection(self, connection: Connection):
    self._add_pending_connection(connection)

    switch_out_topics = set(self.out_topics.items())
    if len(switch_out_topics) > 0: await connection.send(OutTopicsChangedMessage(switch_out_topics, set()))

    switch_addresses = set(self.addresses.items())
    if len(switch_addresses) > 0: await connection.send(AddressesChangedMessage(switch_addresses, set()))
  
    added_out_topics = self.out_topics.add_many(connection.get_priced_out_topics())
    if len(added_out_topics) > 0: await self.broadcast(OutTopicsChangedMessage(added_out_topics, set()))

    added_addresses = self.addresses.add_many(connection.get_priced_addresses())
    if len(added_addresses) > 0: await self.broadcast(AddressesChangedMessage(added_addresses, set()))

    added_in_topics = self.in_topics.add_many(connection.in_topics)
    if len(added_in_topics) > 0: await self.request_in_topics_change(added_in_topics, set())

    self.connections.append(connection)
  
  async def remove_connection(self, connection: Connection):
    if connection in self.connections: self.connections.remove(connection)
    self._remove_pending_connection(connection)
    if connection in self.connection_receiving_tasks: self.connection_receiving_tasks[connection].cancel()

    recv_topics = connection.recv_topics
    removed_topics, updated_topics = self.out_topics.remove_many(connection.get_priced_out_topics())
    updated_in_topics = recv_topics - removed_topics

    if len(updated_in_topics) > 0:
      await self.request_in_topics_change(set(updated_in_topics), set())
    
    if len(removed_topics) > 0 or len(updated_topics) > 0:
      await self.broadcast(OutTopicsChangedMessage(updated_topics, removed_topics))

    removed_addresses, updated_addresses = self.addresses.remove_many(connection.get_priced_addresses())
    if len(removed_addresses) > 0 or len(updated_addresses) > 0:
      await self.broadcast(AddressesChangedMessage(updated_addresses, removed_addresses))

  async def send_to(self, message: Message, connections: list[Connection]): 
    for connection in connections: await connection.send(message)
  async def broadcast(self, message: Message): await self.send_to(message, self.connections)
  
  async def send_remove_in_topic(self, topic: int):
    await self.send_to(InTopicsChangedMessage(set(), set([topic])), [ conn for conn in self.connections if topic in conn.recv_topics ])

  async def request_in_topics_change(self, add_topics: set[int], remove_topics: set[int]):
    remove_topics_set = set(remove_topics)
    change_map: dict[Connection, InTopicsChangedMessage] = {}

    for topic in add_topics:
      best_connection = min(self.connections, key=lambda connection: connection.out_topics.get(topic, float('inf')))
      if topic not in best_connection.out_topics: continue
      if best_connection not in change_map: change_map[best_connection] = InTopicsChangedMessage(set(), set())
      change_map[best_connection].add.add(topic)
    
    if len(remove_topics_set) > 0:
      for conn in self.connections:
        remove_sub = conn.recv_topics.intersection(remove_topics_set)
        if len(remove_sub) > 0:
          if conn not in change_map: change_map[conn] = InTopicsChangedMessage(set(), set())
          for topic in remove_sub: change_map[conn].remove.add(topic)
    
    for conn, message in change_map.items(): await conn.send(message)

  async def on_in_topics_changed(self, message: InTopicsChangedMessage, origin: Connection):
    # todo: control stream
    final_add = self.in_topics.add_many(message.add)
    final_remove = self.in_topics.remove_many(message.remove)

    for control_message in [ self.stream_controls[topic].to_message(topic) for topic in message.add if topic in self.stream_controls ]: 
      await origin.send(control_message) 

    await self.request_in_topics_change(final_add, final_remove)

  async def on_addressed_message(self, message: AddressedMessage, origin: Connection):
    if message.address not in self.addresses: return
    address_cost = self.addresses.get(message.address)
    found_conn = next(( conn for conn in self.connections if conn.addresses.get(message.address, -1) == address_cost ), None)
    if found_conn is not None: await found_conn.send(message)

  async def on_stream_message(self, message: TopicMessage, origin: Connection):
    await self.send_to(message, [ connection for connection in self.connections if connection != origin and message.topic in connection.in_topics])

  async def on_out_topics_changed(self, message: OutTopicsChangedRecvMessage, origin: Connection):
    out_topics_added, out_topics_removed = self.out_topics.change_many(message.add, message.remove)
    if len(out_topics_added) > 0 or len(out_topics_removed) > 0:
      await self.send_to(OutTopicsChangedMessage(out_topics_added, out_topics_removed), [ conn for conn in self.connections if conn != origin ])

    resub_topics = set()
    for pt in message.add:
      if pt.id in self.in_topics:
        topic_provider = next((conn for conn in self.connections if pt.id in conn.recv_topics), None)
        if topic_provider is None or topic_provider.out_topics[pt.id] > pt.cost: 
          resub_topics.add(pt.id)
    await self.request_in_topics_change(resub_topics, resub_topics) # resub to the better providers

  async def on_addresses_changed(self, message: AddressesChangedRecvMessage, origin: Connection):
    addresses_added, addresses_removed = self.addresses.change_many(message.add, message.remove)
    if len(addresses_added) > 0 or len(addresses_removed) > 0:
      await self.send_to(AddressesChangedMessage(addresses_added, addresses_removed), [ conn for conn in self.connections if conn != origin ])

  async def handle_message(self, message: Message, origin: Connection):
    if isinstance(message, TopicMessage):
      if isinstance(message, TopicControlMessage):
        self.stream_controls[message.topic] = message.to_data()
      await self.on_stream_message(message, origin)
    elif isinstance(message, AddressedMessage):
      await self.on_addressed_message(message, origin)
    elif isinstance(message, InTopicsChangedMessage):
      await self.on_in_topics_changed(message, origin)
    elif isinstance(message, OutTopicsChangedRecvMessage):
      await self.on_out_topics_changed(message, origin)
    elif isinstance(message, AddressesChangedRecvMessage):
      await self.on_addresses_changed(message, origin)
    else:
      assert type(message) not in [ OutTopicsChangedMessage, AddressesChangedMessage ], "Message type should never be received (sender only)!"
      logging.warning(f"Unhandled message {message}")

  async def start(self):
    assert len(self.connections) == len(self.pending_connections), "Switch has non receiving connection!"
    try:
      while True:
        await self.connections_pending.wait()
        connection = self.pending_connections[0]
        self.connection_receiving_tasks[connection] = asyncio.create_task(self._run_connection_receiving(connection))
        self._remove_pending_connection(connection)
    finally:
      for connection in self.connections: await self.remove_connection(connection)

  async def _run_connection_receiving(self, connection: Connection):
    try: 
      while True: 
        message = await connection.recv()
        await self.handle_message(message, connection)
    except Exception as e: logging.error(f"Error receiving from connection: {e}")
    finally: 
      await self.remove_connection(connection)

  def _add_pending_connection(self, connection: Connection):
    self.pending_connections.append(connection)
    self.connections_pending.set()
  def _remove_pending_connection(self, connection: Connection):
    if connection in self.pending_connections: self.pending_connections.remove(connection)
    if len(self.pending_connections) == 0: self.connections_pending.clear()

class IPCSwitch(Switch):
  bind_address: RemoteAddress
  listening: bool

  def __init__(self, bind_address: RemoteAddress):
    super().__init__()
    self.bind_address = bind_address
    self.listening = asyncio.Event()

  async def start_listening(self):
    try:
      self.listening.set()

      loop = asyncio.get_event_loop()
      listener = mpconn.Listener(self.bind_address)
      logging.info(f"Listening on {self.bind_address}")

      while True:
        conn = await loop.run_in_executor(None, listener.accept)
        logging.info(f"Accepted connection!")
        self.add_connection(IPCConnection(conn))
    finally:
      listener.close()
      self.listening.clear()
