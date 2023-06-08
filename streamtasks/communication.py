from typing import Union, Optional, Any
from multiprocessing.connection import Connection
from abc import ABC, abstractmethod, abstractstaticmethod
from dataclasses import dataclass
from typing_extensions import Self

class Message(ABC):
  pass

@dataclass
class StreamMessage(Message):
  topic: int
  data: Any

@dataclass
class SubscribeMessage(Message):
  topic: int

@dataclass
class UnsubscribeMessage(Message):
  topic: int

@dataclass
class ProvidesMessage(Message):
  add_topics: set[int]
  remove_topics: set[int]

class TopicConnection(ABC):
  in_topics: set[int]
  out_topics: set[int]
  __deleted__: bool
  ignore_provides: bool

  def __init__(self):
    self.in_topics, self.out_topics = set(), set()
    self.__deleted__ = False
    self.ignore_internal = False

  def __del__(self):
    self.close()

  def close(self):
    self.__deleted__ = True

  @abstractmethod
  def send(self, message: Message):
    pass

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
      self.out_topics = self.out_topics.union(message.add_topics).difference(message.remove_topics)
      if self.ignore_internal:
        return None

    return message

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

  def send(self, message: Message):
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

  def send(self, message: Message):
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

class TopicSwitch:
  subscription_counter: dict[int, int]
  provides: dict[int, int]
  connections: list[TopicConnection]

  def __init__(self):
    self.subscription_counter = {}
    self.connections = []
    self.provides = {}

  def add_connection(self, connection: TopicConnection):
    assert len(connection.out_topics) == 0, "Connection must not provide topics, before adding it to the switch"
    self.connections.append(connection)
  
  def remove_connection(self, connection: TopicConnection):
    self.connections.remove(connection)

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

  def send_to_many(self, message: Message, connections: list[TopicConnection]): 
    for connection in connections: connection.send(message)

  def subscribe(self, message: SubscribeMessage, origin: TopicConnection):
    if message.topic not in self.subscription_counter: self.subscription_counter[message.topic] = 0
    self.subscription_counter[message.topic] += 1
    if self.subscription_counter[message.topic] != 1:
      return

    self.send_to_many(message, [ connection for connection in self.connections if connection != origin and message.topic in connection.out_topics ])

  def unsubscribe(self, message: UnsubscribeMessage, origin: TopicConnection):
    assert message.topic in self.subscription_counter and self.subscription_counter[message.topic], "Topic not subscribed"
    self.subscription_counter[message.topic] -= 1
    if self.subscription_counter[message.topic] != 0:
      return

    self.send_to_many(message, [ connection for connection in self.connections if connection != origin and message.topic in connection.out_topics ])

  def distribute(self, message: StreamMessage, origin: TopicConnection):
    self.send_to_many(message, [ connection for connection in self.connections if connection != origin and message.topic in connection.in_topics])

  def broadcast(self, message: Message):
    self.send_to_many(message, self.connections)

  def remove_connection(self, connection: TopicConnection):
    removed_topics = set()
    for topic in connection.out_topics:
      current_count = self.provides.get(topic, 0)
      if current_count == 1:
        removed_topics.add(topic)
      self.provides[topic] = max(current_count - 1, 0)
    
    self.connections.remove(connection)
    self.broadcast(ProvidesMessage(set(), removed_topics))

  def on_provides(self, message: ProvidesMessage, origin: TopicConnection):
    provides_added, provides_removed = set(), set()
    for topic in message.add_topics:
      current_count = self.provides.get(topic, 0)
      if current_count == 0:
        provides_added.add(topic)
      self.provides[topic] = current_count + 1

    for topic in message.remove_topics:
      current_count = self.provides.get(topic, 0)
      if current_count == 1:
        provides_removed.add(topic)
      self.provides[topic] = max(current_count - 1, 0) 

    if len(provides_added) > 0 or len(provides_removed) > 0:
      # NOTE: This might cause problems
      self.send_to_many(ProvidesMessage(provides_added, provides_removed), [ connection for connection in self.connections if connection != origin ])

    for topic in message.add_topics:
      if self.subscription_counter.get(topic, 0) > 0:
        origin.send(SubscribeMessage(topic))

  def handle_message(self, message: Message, origin: TopicConnection):
    if isinstance(message, SubscribeMessage):
      self.subscribe(message, origin)
    elif isinstance(message, UnsubscribeMessage):
      self.unsubscribe(message, origin)
    elif isinstance(message, StreamMessage):
      self.distribute(message, origin)
    elif isinstance(message, ProvidesMessage):
      self.on_provides(message, origin)
    else:
      self.broadcast(message)