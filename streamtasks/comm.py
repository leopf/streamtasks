from streamtasks.messages import *

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
  out_topics: dict[int, int]
  recv_topics: set[int]
  cost: int

  deleted: bool
  ignore_internal: bool

  def __init__(self, cost: int = 1):
    self.in_topics, self.out_topics = set(), dict()
    self.recv_topics = set()
    self.deleted = False
    self.ignore_internal = False
    self.cost = cost

  def __del__(self):
    self.close()

  def close(self):
    self.deleted = True

  def get_priced_topics(self, topics: set[int] = None) -> set[PricedTopic]:
    if topics is None:
      return set(PricedTopic(topic, cost) for topic, cost in self.out_topics.items())
    else:
      return set(PricedTopic(topic, self.out_topics[topic]) for topic in topics if topic in self.out_topics)

  def send(self, message: Message):
    if isinstance(message, InTopicsChangedMessage):
      itc_message: InTopicsChangedMessage = message
      self.recv_topics = self.recv_topics.union(itc_message.add).difference(itc_message.remove)
    elif isinstance(message, OutTopicsChangedMessage):
      otc_message: OutTopicsChangedMessage = message
      message = OutTopicsChangedMessage(set(PricedTopic(pt.topic, pt.cost + self.cost) for pt in otc_message.add), otc_message.remove)
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
      message = OutTopicsChangedMessage(set(PricedTopic(pt.topic, pt.cost + self.cost) for pt in otc_message.add), otc_message.remove)
      for topic in message.remove: self.out_topics.pop(wt.topic, None)
      for wt in message.add: self.out_topics[wt.topic] = wt.cost

      if self.ignore_internal:
        return None

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
  in_topics: dict[int, int]
  out_topics: dict[int, SwitchTopicInfo]

  stream_controls: dict[int, StreamControlData]
  connections: list[Connection]

  def __init__(self):
    self.connections = []
    self.in_topics = {}
    self.out_topics = {}
    self.stream_controls = {}

  def add_connection(self, connection: Connection):
    new_provides = set(PricedTopic(topic, data.cost) for topic, data in self.out_topics.items() if data.count > 0)
    if len(new_provides) > 0: connection.send(OutTopicsChangedMessage(new_provides, set()))
  
    added_topics = self.add_out_topics(connection.out_topics)
    if len(added_topics) > 0: self.broadcast(OutTopicsChangedMessage(added_topics, set()))
    # TODO: respect in topics
    self.connections.append(connection)
  
  def remove_connection(self, connection: Connection):
    self.connections.remove(connection)
    recv_topics = connection.recv_topics # topics we were receiving from the connection
    removed_topics, updated_topics = self.remove_out_topics(connection.get_priced_topics())
    updated_in_topics = recv_topics - removed_topics

    # TODO: better way to do this
    for topic in updated_in_topics:
      self.send_add_in_topic(topic)
    
    if len(removed_topics) > 0 or len(updated_topics) > 0:
      self.broadcast(OutTopicsChangedMessage(updated_topics, removed_topics))

  def process(self):
    removing_connections = []

    for connection in self.connections:
      message = connection.recv()
      if connection.deleted:
        removing_connections.append(connection)
      elif message is None:
        continue
      else:
        self.handle_message(message, connection)

    for connection in removing_connections: self.remove_connection(connection)

  def send_to(self, message: Message, connections: list[Connection]): 
    for connection in connections: connection.send(message)
  def broadcast(self, message: Message): self.send_to(message, self.connections)

  def remove_out_topics(self, topics: Iterable[PricedTopic]):
    final_removed, updated = set(), set()
    for pt in topics:
      current_data: Optional[SwitchTopicInfo] = self.out_topics.get(pt.topic, None)
      if current_data is None: continue # NOTE: this should not happen
      elif current_data.count == 1: 
        final_removed.add(pt.topic)
        self.out_topics.pop(pt.topic, None)
      else:
        current_data.count = max(current_data.count - 1, 0)
        if current_data.cost == pt.cost:
          new_cost = min([ conn.out_topics.get(pt.topic, float("inf")) for conn in self.connections ], default=float('inf'))
          assert new_cost != float('inf'), "There should be at least one provider for the topic, but there is none."
          current_data.cost = new_cost
          updated.add(PricedTopic(pt.topic, new_cost))
    return final_removed, updated
  
  def add_out_topics(self, topics: Iterable[PricedTopic]):
    final = set()
    for wt in topics:
      current_data = self.out_topics.get(wt.topic, SwitchTopicInfo(wt.cost, 0))
      if current_data.count == 0: final.add(wt)
      elif current_data.cost > wt.cost:
        final.add(wt)
        current_data.cost = wt.cost
      current_data.count += 1
      self.out_topics[wt.topic] = current_data
    return final

  def add_in_topics(self, topics: Iterable[int]):
    final = set()
    for topic in topics:
      current_count = self.in_topics.get(topic, 0)
      if current_count == 0: final.add(topic)
      self.in_topics[topic] = current_count + 1
    return final

  def remove_in_topics(self, topics: Iterable[int]):
    final = set()
    for topic in topics:
      current_count = self.in_topics.get(topic, 0)
      if current_count == 1: final.add(topic)
      self.in_topics[topic] = max(current_count - 1, 0)
    return final

  def send_remove_in_topic(self, topic: int):
    self.send_to(InTopicsChangedMessage(set(), set([topic])), [ conn for conn in self.connections if topic in conn.recv_topics ])

  def send_add_in_topic(self, topic: int):
    best_connection = min(self.connections, key=lambda connection: connection.out_topics.get(topic, float('inf')))
    if topic in best_connection.out_topics:
      best_connection.send(InTopicsChangedMessage(set([topic]), set()))

  def on_in_topics_changed(self, message: InTopicsChangedMessage, origin: Connection):
    # todo: control stream
    final_add = self.add_in_topics(message.add)
    final_remove = self.remove_in_topics(message.remove)

    for control_message in [ self.stream_controls[topic].to_message(topic) for topic in message.add if topic in self.stream_controls ]: 
      origin.send(control_message) 
    for topic in final_remove: self.send_remove_in_topic(topic)
    for topic in final_add: self.send_add_in_topic(topic)

  def on_distribute(self, message: StreamMessage, origin: Connection):
    self.send_to(message, [ connection for connection in self.connections if connection != origin and message.topic in connection.in_topics])

  def on_provides(self, message: OutTopicsChangedMessage, origin: Connection):
    provides_removed, provides_updated = self.remove_out_topics(message.remove)
    provides_added = merge_priced_topics(list(self.add_out_topics(message.add)) + list(provides_updated))

    if len(provides_added) > 0 or len(provides_removed) > 0:
      # NOTE: This might cause problems
      self.send_to(OutTopicsChangedMessage(provides_added, provides_removed), [ conn for conn in self.connections if conn != origin ])

    for wt in message.add:
      if self.in_topics.get(wt.topic, 0) > 0:
        topic_provider = next((conn for conn in self.connections if wt.topic in conn.recv_topics), None)
        if topic_provider is None or topic_provider.out_topics[wt.topic] > wt.cost: # resub to the better provider
          self.send_remove_in_topic(wt.topic)
          self.send_add_in_topic(wt.topic)

  def handle_message(self, message: Message, origin: Connection):
    if isinstance(message, InTopicsChangedMessage):
      self.on_in_topics_changed(message, origin)
    elif isinstance(message, StreamMessage):
      if isinstance(message, StreamControlMessage):
        self.stream_controls[message.topic] = message.to_data()
      self.on_distribute(message, origin)
    elif isinstance(message, OutTopicsChangedMessage):
      self.on_provides(message, origin)
    else:
      self.broadcast(message)

class IPCSwitch(Switch):
  bind_address: RemoteAddress
  listening: bool

  def __init__(self, bind_address: RemoteAddress):
    super().__init__()
    self.bind_address = bind_address
    self.listening = False

  def signal_stop(self):
    self.listening = False

  async def start_listening(self):
    self.listening = True

    loop = asyncio.get_event_loop()
    listener = mpconn.Listener(self.bind_address)
    logging.info(f"Listening on {self.bind_address}")

    while self.listening:
      conn = await loop.run_in_executor(None, listener.accept)
      logging.info(f"Accepted connection!")
      self.add_connection(IPCConnection(conn))