from streamtasks.comm.types import *
from streamtasks.comm.helpers import *

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

  closed: bool
  ignore_internal: bool

  def __init__(self, cost: int = 1):
    self.in_topics = set()
    self.out_topics = dict()
    self.addresses = dict()
    self.recv_topics = set()

    self.closed = False

    assert cost > 0, "Cost must be greater than 0"
    self.cost = cost

  def __del__(self):
    self.close()

  def close(self):
    self.closed = True

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

  def send(self, message: Message):
    if isinstance(message, InTopicsChangedMessage):
      itc_message: InTopicsChangedMessage = message
      self.recv_topics = self.recv_topics.union(itc_message.add).difference(itc_message.remove)
    elif isinstance(message, OutTopicsChangedMessage):
      otc_message: OutTopicsChangedMessage = message
      message = OutTopicsChangedMessage(set(PricedId(pt.id, pt.cost + self.cost) for pt in otc_message.add), otc_message.remove)
    elif isinstance(message, AddressesChangedMessage):
      ac_message: AddressesChangedMessage = message
      message = AddressesChangedMessage(set(PricedId(pa.id, pa.cost + self.cost) for pa in ac_message.add), ac_message.remove)
    self._send(message)

  def recv(self) -> Optional[Message]:
    message = self._recv()
    if message is None:
      return None

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
        set(PricedId(a, self.addresses[a]) for a in ac_message.remove if t in self.addresses))
      for address in ac_message.remove: self.addresses.pop(address, None)
      for pa in message.add: self.addresses[pa.id] = pa.cost

    return message

  @abstractmethod
  def _send(self, message: Message):
    pass

  @abstractmethod
  def _recv(self) -> Optional[Message]:
    pass

class IPCConnection(Connection):
  connection: mpconn.Connection

  def __init__(self, connection: mpconn.Connection, cost: Optional[int] = None):
    super().__init__(cost)
    self.connection = connection

  def close(self):
    super().close()
    self.connection.close()

  def _send(self, message: Message):
    if not self.check_closed():
      self.connection.send(message)

  def _recv(self) -> Optional[Message]:
    if self.check_closed():
      return None

    if self.connection.poll():
      return self.connection.recv()
    else:
      return None

  def check_closed(self):
    if self.connection.closed:
      self.close()
    return self.connection.closed

class ListConnection(Connection):
  out_messages: list[Message]
  in_messages: list[Message]
  close_ref: list[bool]

  def __init__(self, close_ref: list[bool], out_messages: list[Message], in_messages: list[Message]):
    super().__init__()
    self.out_messages = out_messages
    self.in_messages = in_messages
    self.close_ref = close_ref

  def close(self):
    super().close()
    self.close_ref[0] = True

  def _send(self, message: Message):
    if self.close_ref[0]:
      self.close()
      return

    self.out_messages.append(message)

  def _recv(self) -> Optional[Message]:
    if self.close_ref[0]:
      self.close()
      return None

    if len(self.in_messages) == 0:
      return None
    else:
      return self.in_messages.pop(0)

def create_local_cross_connector() -> tuple[Connection, Connection]:
  close_ref = [False]
  messages_a, messages_b = [], []
  return ListConnection(close_ref, messages_a, messages_b), ListConnection(close_ref, messages_b, messages_a)

def connect_to_listener(address: RemoteAddress) -> Optional[IPCConnection]:
  logging.info(f"Connecting to {address}")
  try:
    conn = IPCConnection(mpconn.Client(address))
    logging.info(f"Connected to {address}")
    return conn
  except Exception:
    logging.error(f"Connection to {address} refused")
    return None

def get_node_socket_path(id: int) -> str:
  if os.name == 'nt':
      return f'\\\\.\\pipe\\streamtasks-{id}'
  else:
      return f'/tmp/streamtasks-{id}.sock'

@dataclass
class SwitchTopicInfo:
  cost: int
  count: int

class Switch:
  in_topics: IdTracker
  out_topics: PricedIdTracker
  addresses: PricedIdTracker

  stream_controls: dict[int, StreamControlData]
  connections: list[Connection]

  def __init__(self):
    self.connections = []
    self.in_topics = IdTracker()
    self.out_topics = PricedIdTracker()
    self.addresses = PricedIdTracker()
    self.stream_controls = {}

  def add_connection(self, connection: Connection):
    switch_out_topics = set(self.out_topics.items())
    if len(switch_out_topics) > 0: connection.send(OutTopicsChangedMessage(switch_out_topics, set()))

    switch_addresses = set(self.addresses.items())
    if len(switch_addresses) > 0: connection.send(AddressesChangedMessage(switch_addresses, set()))
  
    added_out_topics = self.out_topics.add_many(connection.get_priced_out_topics())
    if len(added_out_topics) > 0: self.broadcast(OutTopicsChangedMessage(added_out_topics, set()))

    added_addresses = self.addresses.add_many(connection.get_priced_addresses())
    if len(added_addresses) > 0: self.broadcast(AddressesChangedMessage(added_addresses, set()))

    added_in_topics = self.in_topics.add_many(connection.in_topics)
    if len(added_in_topics) > 0: self.request_in_topics_change(added_in_topics, set())

    self.connections.append(connection)
  
  def remove_connection(self, connection: Connection):
    self.connections.remove(connection)
    recv_topics = connection.recv_topics
    removed_topics, updated_topics = self.out_topics.remove_many(connection.get_priced_out_topics())
    updated_in_topics = recv_topics - removed_topics

    if len(updated_in_topics) > 0:
      self.request_in_topics_change(set(updated_in_topics), set())
    
    if len(removed_topics) > 0 or len(updated_topics) > 0:
      self.broadcast(OutTopicsChangedMessage(updated_topics, removed_topics))

    removed_addresses, updated_addresses = self.addresses.remove_many(connection.get_priced_addresses())
    if len(removed_addresses) > 0 or len(updated_addresses) > 0:
      self.broadcast(AddressesChangedMessage(updated_addresses, removed_addresses))

  def process(self):
    removing_connections = []

    for connection in self.connections:
      message = connection.recv()
      if connection.closed:
        removing_connections.append(connection)
      elif message is None:
        continue
      else:
        self.handle_message(message, connection)

    for connection in removing_connections: self.remove_connection(connection)

  def send_to(self, message: Message, connections: list[Connection]): 
    for connection in connections: connection.send(message)
  def broadcast(self, message: Message): self.send_to(message, self.connections)
  
  def send_remove_in_topic(self, topic: int):
    self.send_to(InTopicsChangedMessage(set(), set([topic])), [ conn for conn in self.connections if topic in conn.recv_topics ])

  def request_in_topics_change(self, add_topics: set[int], remove_topics: set[int]):
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
    
    for conn, message in change_map.items(): conn.send(message)

  def on_in_topics_changed(self, message: InTopicsChangedMessage, origin: Connection):
    # todo: control stream
    final_add = self.in_topics.add_many(message.add)
    final_remove = self.in_topics.remove_many(message.remove)

    for control_message in [ self.stream_controls[topic].to_message(topic) for topic in message.add if topic in self.stream_controls ]: 
      origin.send(control_message) 

    self.request_in_topics_change(final_add, final_remove)

  def on_addressed_message(self, message: AddressedMessage, origin: Connection):
    if message.address not in self.addresses: return
    address_cost = self.addresses.get(message.address)
    found_conn = next(( conn for conn in self.connections if conn.addresses.get(message.address, -1) == address_cost ), None)
    if found_conn is not None: found_conn.send(message)

  def on_stream_message(self, message: StreamMessage, origin: Connection):
    self.send_to(message, [ connection for connection in self.connections if connection != origin and message.topic in connection.in_topics])

  def on_out_topics_changed(self, message: OutTopicsChangedRecvMessage, origin: Connection):
    out_topics_added, out_topics_removed = self.out_topics.change_many(message.add, message.remove)
    if len(out_topics_added) > 0 or len(out_topics_removed) > 0:
      self.send_to(OutTopicsChangedMessage(out_topics_added, out_topics_removed), [ conn for conn in self.connections if conn != origin ])

    resub_topics = set()
    for pt in message.add:
      if pt.id in self.in_topics:
        topic_provider = next((conn for conn in self.connections if pt.id in conn.recv_topics), None)
        if topic_provider is None or topic_provider.out_topics[pt.id] > pt.cost: 
          resub_topics.add(pt.id)
    self.request_in_topics_change(resub_topics, resub_topics) # resub to the better providers

  def on_addresses_changed(self, message: AddressesChangedRecvMessage, origin: Connection):
    addresses_added, addresses_removed = self.addresses.change_many(message.add, message.remove)
    if len(addresses_added) > 0 or len(addresses_removed) > 0:
      self.send_to(AddressesChangedMessage(addresses_added, addresses_removed), [ conn for conn in self.connections if conn != origin ])

  def handle_message(self, message: Message, origin: Connection):
    if isinstance(message, StreamMessage):
      if isinstance(message, StreamControlMessage):
        self.stream_controls[message.topic] = message.to_data()
      self.on_stream_message(message, origin)
    elif isinstance(message, AddressedMessage):
      self.on_addressed_message(message, origin)
    elif isinstance(message, InTopicsChangedMessage):
      self.on_in_topics_changed(message, origin)
    elif isinstance(message, OutTopicsChangedRecvMessage):
      self.on_out_topics_changed(message, origin)
    elif isinstance(message, AddressesChangedRecvMessage):
      self.on_addresses_changed(message, origin)
    else:
      assert type(message) not in [ OutTopicsChangedMessage, AddressesChangedMessage ], "Message type should never be received (sender only)!"
      logging.warning(f"Unhandled message {message}")

class IPCSwitch(Switch):
  bind_address: RemoteAddress
  listening: bool

  def __init__(self, bind_address: RemoteAddress):
    super().__init__()
    self.bind_address = bind_address
    self.listening = False

  async def start_listening(self, stop_signal: asyncio.Event):
    self.listening = True

    loop = asyncio.get_event_loop()
    listener = mpconn.Listener(self.bind_address)
    logging.info(f"Listening on {self.bind_address}")

    while not stop_signal.is_set():
      conn = await loop.run_in_executor(None, listener.accept)
      logging.info(f"Accepted connection!")
      self.add_connection(IPCConnection(conn))

    listener.close()
    self.listening = False

def create_switch_processing_task(switch: Switch, stop_signal: asyncio.Event) -> tuple[asyncio.Task, asyncio.Event]:
  async def process_switch():
    while not stop_signal.is_set():
      switch.process()
      await asyncio.sleep(0.001)
  return asyncio.create_task(process_switch())
