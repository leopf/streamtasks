from typing import Union, Optional, Any, Iterable
from multiprocessing.connection import Connection, Client, Listener
from abc import ABC, abstractmethod, abstractstaticmethod
from dataclasses import dataclass
from typing_extensions import Self
import logging

RemoteAddress = Union[str, tuple[str, int]]

class Message(ABC):
  pass


class StreamMessage(Message, ABC):
  topic: int

@dataclass
class StreamDataMessage(StreamMessage):
  topic: int
  data: Any

@dataclass
class StreamPauseMessage(StreamMessage):
  topic: int
  paused: bool

@dataclass
class SubscribeMessage(Message):
  topic: int

@dataclass
class UnsubscribeMessage(Message):
  topic: int

@dataclass
class PricedTopic:
  topic: int
  cost: int

  def __hash__(self):
    return self.cost | self.topic << 32

@dataclass
class ProvidesMessage(Message):
  add_topics: set[PricedTopic]
  remove_topics: set[int]

class TopicConnection(ABC):
  in_topics: set[int]
  out_topics: dict[int, int]
  subscribed_topics: set[int]

  __deleted__: bool
  ignore_internal: bool

  def __init__(self):
    self.in_topics, self.out_topics = set(), dict()
    self.__deleted__ = False
    self.ignore_internal = False
    self.subscribed_topics = set()

  def __del__(self):
    self.close()

  def close(self):
    self.__deleted__ = True

  def send(self, message: Message):
    if isinstance(message, SubscribeMessage):
      self.subscribed_topics.add(message.topic)
    elif isinstance(message, UnsubscribeMessage):
      if message.topic in self.subscribed_topics:
        self.subscribed_topics.remove(message.topic)
      else:
        return
    self._send(message)

  def recv(self) -> Optional[Message]:
    message = self._recv()
    if message is None:
      return None

    if isinstance(message, SubscribeMessage):
      if message.topic in self.in_topics:
        return None
      self.in_topics.add(message.topic)
    elif isinstance(message, UnsubscribeMessage):
      if message.topic not in self.in_topics:
        return None
      self.in_topics.remove(message.topic)
    elif isinstance(message, ProvidesMessage):
      for topic in message.remove_topics: self.out_topics.pop(wt.topic, None)
      for wt in message.add_topics: self.out_topics[wt.topic] = wt.cost

      if self.ignore_internal:
        return None

    return message

  @abstractmethod
  def _send(self, message: Message):
    pass

  @abstractmethod
  def _recv(self) -> Optional[Message]:
    pass

class IPCTopicConnection(TopicConnection):
  connection: Connection

  def __init__(self, connection: Connection):
    super().__init__()
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

class PushTopicConnection(TopicConnection):
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

def create_local_cross_connector() -> tuple[TopicConnection, TopicConnection]:
  close_ref = [False]
  messages_a, messages_b = [], []
  return PushTopicConnection(close_ref, messages_a, messages_b), PushTopicConnection(close_ref, messages_b, messages_a)

def connect_to_listener(address: RemoteAddress) -> Optional[IPCTopicConnection]:
  logging.info(f"Connecting to {address}")
  try:
    conn = IPCTopicConnection(Client(address))
    logging.info(f"Connected to {address}")
    return conn
  except ConnectionRefusedError:
    logging.error(f"Connection to {address} refused")
    return None

def get_node_socket_path(id: int) -> str:
  if os.name == 'nt':
      return f'\\\\.\\pipe\\streamtasks-{id}'
  else:
      return f'/run/streamtasks-{id}.sock'

class TopicSwitch:
  subscription_counter: dict[int, int]
  provides: dict[int, int]
  connections: list[TopicConnection]

  def __init__(self):
    self.subscription_counter = {}
    self.connections = []
    self.provides = {}

  def add_connection(self, connection: TopicConnection):
    added_topics = self.add_topics(connection.out_topics)
    if len(added_topics) > 0:
      self.broadcast(ProvidesMessage(added_topics, set()))
    self.connections.append(connection)
  
  def remove_connection(self, connection: TopicConnection):
    self.connections.remove(connection)
 
    subscribed_topics = connection.subscribed_topics
    removed_topics = self.remove_topics(connection.out_topics)
    compensate_topics = subscribed_topics - removed_topics

    for topic in compensate_topics:
      self.subscribe(topic)
    
    if len(removed_topics) > 0:
      self.broadcast(ProvidesMessage(set(), removed_topics))

  def process(self):
    removing_connections = []

    for connection in self.connections:
      message = connection.recv()
      if connection.__deleted__:
        removing_connections.append(connection)
      elif message is None:
        continue
      else:
        self.handle_message(message, connection)

    for connection in removing_connections: self.remove_connection(connection)

  def send_to(self, message: Message, connections: list[TopicConnection]): 
    for connection in connections: connection.send(message)
  def broadcast(self, message: Message): self.send_to(message, self.connections)

  def remove_topics(self, topics: Iterable[int]):
    final = set()
    for topic in topics:
      current_count = self.provides.get(topic, 0)
      if current_count == 1:
        final.add(topic)
      self.provides[topic] = max(current_count - 1, 0)
    return final
  
  def add_topics(self, topics: Iterable[PricedTopic]):
    final = set()
    for wt in topics:
      current_count = self.provides.get(wt.topic, 0)
      if current_count == 0:
        final.add(wt)
      self.provides[wt.topic] = current_count + 1
    return final

  def subscribe(self, topic: int):
    best_connection = min(self.connections, key=lambda connection: connection.out_topics.get(topic, float('inf')))
    if topic in best_connection.out_topics:
      best_connection.send(SubscribeMessage(topic))

  def unsubscribe(self, topic: int):
    self.send_to(UnsubscribeMessage(topic), [ conn for conn in self.connections if topic in conn.subscribed_topics ])

  def on_subscribe(self, message: SubscribeMessage, origin: TopicConnection):
    new_count = self.subscription_counter.get(message.topic, 0) + 1
    self.subscription_counter[message.topic] = new_count
    if new_count == 1: self.subscribe(message.topic)

  def on_unsubscribe(self, message: UnsubscribeMessage, origin: TopicConnection):
    new_count = self.subscription_counter.get(message.topic, 0) - 1
    assert new_count >= 0, "Topic not subscribed"
    self.subscription_counter[message.topic] = new_count
    if new_count == 0: self.unsubscribe(message.topic)

  def on_distribute(self, message: StreamMessage, origin: TopicConnection):
    self.send_to(message, [ connection for connection in self.connections if connection != origin and message.topic in connection.in_topics])

  def on_provides(self, message: ProvidesMessage, origin: TopicConnection):
    provides_added, provides_removed = self.add_topics(message.add_topics), self.remove_topics(message.remove_topics)

    if len(provides_added) > 0 or len(provides_removed) > 0:
      # NOTE: This might cause problems
      self.send_to(ProvidesMessage(provides_added, provides_removed), [ conn for conn in self.connections if conn != origin ])

    for wt in message.add_topics:
      if self.subscription_counter.get(wt.topic, 0) > 0:
        topic_provider = next((conn for conn in self.connections if wt.topic in conn.subscribed_topics), None)
        if topic_provider is None or topic_provider.out_topics[wt.topic] > wt.cost: # resub to the better provider
          self.unsubscribe(wt.topic)
          self.subscribe(wt.topic)

  def handle_message(self, message: Message, origin: TopicConnection):
    if isinstance(message, SubscribeMessage):
      self.on_subscribe(message, origin)
    elif isinstance(message, UnsubscribeMessage):
      self.on_unsubscribe(message, origin)
    elif isinstance(message, StreamMessage):
      self.on_distribute(message, origin)
    elif isinstance(message, ProvidesMessage):
      self.on_provides(message, origin)
    else:
      self.broadcast(message)

class IPCTopicSwitch(TopicSwitch):
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
    listener = Listener(self.bind_address)
    while self.listening:
      conn = await loop.run_in_executor(None, listener.accept)
      logging.info(f"Accepted connection!")
      self.add_connection(IPCTopicConnection(conn))