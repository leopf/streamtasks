from typing import Any, Callable, Union
from streamtasks.env import DEBUG_SER
from streamtasks.net.helpers import PricedIdTracker
from streamtasks.net.serialization import RawData
from streamtasks.net.serialization import serialize_message, deserialize_message
from streamtasks.utils import IdTracker
from abc import ABC, abstractmethod
import logging
import asyncio

from streamtasks.net.messages import AddressedMessage, AddressesChangedMessage, AddressesChangedRecvMessage, DataMessage, InTopicsChangedMessage, Message, OutTopicsChangedMessage, OutTopicsChangedRecvMessage, PricedId, TopicControlData, TopicControlMessage, TopicDataMessage, TopicMessage

DAddress = Union[str, int] # dynamic address, which allows names or ints
Endpoint = tuple[DAddress, int]
EndpointOrAddress = DAddress | Endpoint

def endpoint_or_address_to_endpoint(ep: EndpointOrAddress, default_port: int):
  return (ep, default_port) if isinstance(ep, (str, int)) else ep

class ConnectionClosedError(Exception):
  def __init__(self, message: str = "Connection closed", origin: BaseException | None = None):
    if origin: super().__init__(message + "\nOrigin: " + str(origin))
    else: super().__init__(message)

if DEBUG_SER():
  def _transform_message(message: Message):
    try: return deserialize_message(serialize_message(message))
    except KeyError: return message
else:
  def _transform_message(message: Message): return message

class Link(ABC):
  def __init__(self, cost: int = 1):
    self.in_topics: set[int] = set()
    self.recv_topics: set[int] = set()
    self.out_topics: dict[int, int] = dict()
    self.addresses: dict[int, int] = dict()
    self.on_closed: list[Callable[[], Any]] = []

    self._closed = False
    self._receiver: asyncio.Task[Message] | None = None

    if cost == 0: raise ValueError("Cost must be greater than 0")
    self._cost = cost

  def __del__(self): self.close()

  @property
  def closed(self): return self._closed

  def close(self):
    if self._closed: return
    self._closed = True
    if self._receiver is not None:
      try: self._receiver.cancel(ConnectionClosedError())
      except asyncio.InvalidStateError: pass
    for handler in self.on_closed: handler()
    self.on_closed.clear()

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
    if self._closed: raise ConnectionClosedError()
    assert not isinstance(message, DataMessage) or isinstance(message.data, RawData), "The message data must be of type raw data!"
    message = _transform_message(message)
    if isinstance(message, InTopicsChangedMessage):
      itc_message: InTopicsChangedMessage = message
      self.recv_topics = self.recv_topics.union(itc_message.add).difference(itc_message.remove)
    elif isinstance(message, OutTopicsChangedMessage):
      otc_message: OutTopicsChangedMessage = message
      message = OutTopicsChangedMessage(set(PricedId(pt.id, pt.cost + self._cost) for pt in otc_message.add), otc_message.remove)
    elif isinstance(message, AddressesChangedMessage):
      ac_message: AddressesChangedMessage = message
      message = AddressesChangedMessage(set(PricedId(pa.id, pa.cost + self._cost) for pa in ac_message.add), ac_message.remove)
    await self._send(message)

  async def recv(self) -> Message:
    if self._closed: raise ConnectionClosedError()
    message = None
    while message is None:
      self._receiver = asyncio.create_task(self._recv())
      try:
        message = await self._receiver
        message = _transform_message(message)
        message = self._process_recv_message(message)
      except asyncio.CancelledError as e:
        if len(e.args) > 0 and isinstance(e.args[0], ConnectionClosedError): raise e.args[0]
        else: raise e
      finally: self._receiver = None
    return message

  @abstractmethod
  async def _send(self, message: Message): pass

  @abstractmethod
  async def _recv(self) -> Message: pass

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
        set(PricedId(pt.id, pt.cost + self._cost) for pt in otc_message.add),
        set(PricedId(t, self.out_topics[t]) for t in otc_message.remove if t in self.out_topics))
      for address in otc_message.remove: self.out_topics.pop(address, None)
      for pt in message.add: self.out_topics[pt.id] = pt.cost

    elif isinstance(message, AddressesChangedMessage):
      ac_message: AddressesChangedMessage = message
      message = AddressesChangedRecvMessage(
        set(PricedId(pa.id, pa.cost + self._cost) for pa in ac_message.add),
        set(PricedId(a, self.addresses[a]) for a in ac_message.remove if a in self.addresses))
      for address in ac_message.remove: self.addresses.pop(address, None)
      for pa in message.add: self.addresses[pa.id] = pa.cost

    return message

class TopicRemappingLink(Link): # NOTE: maybe this should just inherit a specific link...
  def __init__(self, link: Link, topic_id_map: dict[int, int]):
    super().__init__()
    self.on_closed.append(link.close)
    link.on_closed.append(self.close)
    self._link = link
    self._topic_id_map = topic_id_map # internal -> external
    self._rev_topic_id_map = {v:k for k, v in topic_id_map.items() } # external -> internal

  async def _recv(self) -> Message: return self._remap_message(await self._link.recv(), self._rev_topic_id_map)
  async def _send(self, message: Message): await self._link.send(self._remap_message(message, self._topic_id_map))

  def _remap_message(self, message: Message, topic_id_map: dict[int, int]):
    if isinstance(message, TopicDataMessage):
      message = TopicDataMessage(topic_id_map.get(message.topic, message.topic), message.data)
    elif isinstance(message, TopicControlMessage):
      message = TopicControlMessage(topic_id_map.get(message.topic, message.topic), message.paused)
    elif isinstance(message, InTopicsChangedMessage):
      message = InTopicsChangedMessage(self._remap_id_set(message.add, topic_id_map), self._remap_id_set(message.remove, topic_id_map))
    elif isinstance(message, OutTopicsChangedRecvMessage):
      message = OutTopicsChangedRecvMessage(self._remap_priced_id_set(message.add, topic_id_map), self._remap_priced_id_set(message.remove, topic_id_map))
    elif isinstance(message, OutTopicsChangedMessage):
      message = OutTopicsChangedMessage(self._remap_priced_id_set(message.add, topic_id_map), self._remap_id_set(message.remove, topic_id_map))
    return message

  def _remap_id_set(self, ids: set[int], topic_id_map: dict[int, int]): return set(topic_id_map.get(t, t) for t in ids)
  def _remap_priced_id_set(self, ids: set[PricedId], topic_id_map: dict[int, int]): return set(PricedId(topic_id_map.get(t.id, t.id), t.cost) for t in ids)


class QueueLink(Link):
  def __init__(self, out_messages: asyncio.Queue[Message], in_messages: asyncio.Queue[Message]):
    super().__init__()
    self.out_messages = out_messages
    self.in_messages = in_messages

  async def _send(self, message: Message): await self.out_messages.put(message)
  async def _recv(self) -> Message:
    result = await self.in_messages.get()
    self.in_messages.task_done()
    return result

class RawQueueLink(QueueLink):
  async def _send(self, message: Message): await self.out_messages.put(serialize_message(message))
  async def _recv(self) -> Message:
    result = await self.in_messages.get()
    self.in_messages.task_done()
    return deserialize_message(result)

def create_queue_connection(raw: bool = False) -> tuple[Link, Link]:
  queue_a, queue_b = asyncio.Queue(), asyncio.Queue()
  if raw: link_a, link_b = RawQueueLink(queue_a, queue_b), RawQueueLink(queue_b, queue_a)
  else: link_a, link_b = QueueLink(queue_a, queue_b), QueueLink(queue_b, queue_a)
  link_a.on_closed.append(link_b.close)
  link_b.on_closed.append(link_a.close)
  return link_a, link_b


class LinkManager:
  def __init__(self): self._link_recv_tasks: dict[Link, asyncio.Task] = {}
  @property
  def links(self): return self._link_recv_tasks.keys()
  def has_link(self, link: Link): return link in self._link_recv_tasks
  def accept_link(self, link: Link, receiver_task: asyncio.Task): self._link_recv_tasks[link] = receiver_task
  def remove_link(self, link: Link):
    if link in self._link_recv_tasks: self._link_recv_tasks.pop(link).cancel()
  def cancel_all(self):
    for task in self._link_recv_tasks.values(): task.cancel()
    self._link_recv_tasks.clear()


class Switch:
  def __init__(self):
    self.link_manager = LinkManager()
    self.in_topics = IdTracker()
    self.out_topics = PricedIdTracker()
    self.addresses = PricedIdTracker()
    self.stream_controls: dict[int, TopicControlData] = {}
  def __del__(self): self.link_manager.cancel_all()

  async def add_local_connection(self) -> Link:
    a, b = create_queue_connection()
    await self.add_link(a)
    return b
  async def add_link(self, link: Link):
    switch_out_topics = set(self.out_topics.items())
    if len(switch_out_topics) > 0: await link.send(OutTopicsChangedMessage(switch_out_topics, set()))

    switch_addresses = set(self.addresses.items())
    if len(switch_addresses) > 0: await link.send(AddressesChangedMessage(switch_addresses, set()))

    added_out_topics = self.out_topics.add_many(link.get_priced_out_topics())
    if len(added_out_topics) > 0: await self.broadcast(OutTopicsChangedMessage(added_out_topics, set()))

    added_addresses = self.addresses.add_many(link.get_priced_addresses())
    if len(added_addresses) > 0: await self.broadcast(AddressesChangedMessage(added_addresses, set()))

    added_in_topics = self.in_topics.add_many(link.in_topics)
    if len(added_in_topics) > 0: await self.request_in_topics_change(added_in_topics, set())

    self.link_manager.accept_link(link, asyncio.create_task(self._run_link_receiving(link)))

  async def remove_link(self, link: Link):
    self.link_manager.remove_link(link)

    recv_topics = link.recv_topics
    removed_topics, updated_topics = self.out_topics.remove_many(link.get_priced_out_topics())
    updated_in_topics = recv_topics - removed_topics

    if len(updated_in_topics) > 0:
      await self.request_in_topics_change(set(updated_in_topics), set())

    if len(removed_topics) > 0 or len(updated_topics) > 0:
      await self.broadcast(OutTopicsChangedMessage(updated_topics, removed_topics))

    removed_addresses, updated_addresses = self.addresses.remove_many(link.get_priced_addresses())
    if len(removed_addresses) > 0 or len(updated_addresses) > 0:
      await self.broadcast(AddressesChangedMessage(updated_addresses, removed_addresses))

  def stop_receiving(self): self.link_manager.cancel_all()
  async def send_to(self, message: Message, links: list[Link]):
    for link in links: await link.send(message)
  async def broadcast(self, message: Message): await self.send_to(message, self.link_manager.links)

  async def send_remove_in_topic(self, topic: int):
    await self.send_to(InTopicsChangedMessage(set(), set([topic])), [ conn for conn in self.link_manager.links if topic in conn.recv_topics ])

  async def request_in_topics_change(self, add_topics: set[int], remove_topics: set[int]):
    remove_topics_set = set(remove_topics)
    change_map: dict[Link, InTopicsChangedMessage] = {}

    for topic in add_topics:
      best_link = min(self.link_manager.links, key=lambda link: link.out_topics.get(topic, float('inf')))
      if topic not in best_link.out_topics: continue
      if best_link not in change_map: change_map[best_link] = InTopicsChangedMessage(set(), set())
      change_map[best_link].add.add(topic)

    if len(remove_topics_set) > 0:
      for conn in self.link_manager.links:
        remove_sub = conn.recv_topics.intersection(remove_topics_set)
        if len(remove_sub) > 0:
          if conn not in change_map: change_map[conn] = InTopicsChangedMessage(set(), set())
          for topic in remove_sub: change_map[conn].remove.add(topic)

    for conn, message in change_map.items(): await conn.send(message)

  async def on_in_topics_changed(self, message: InTopicsChangedMessage, origin: Link):
    # todo: control stream
    final_add = self.in_topics.add_many(message.add)
    final_remove = self.in_topics.remove_many(message.remove)

    for control_message in [ self.stream_controls[topic].to_message(topic) for topic in message.add if topic in self.stream_controls ]:
      await origin.send(control_message)

    await self.request_in_topics_change(final_add, final_remove)

  async def on_addressed_message(self, message: AddressedMessage, origin: Link):
    if message.address not in self.addresses: return
    address_cost = self.addresses.get(message.address)
    found_conn = next(( conn for conn in self.link_manager.links if conn.addresses.get(message.address, -1) == address_cost ), None)
    if found_conn is not None: await found_conn.send(message)

  async def on_stream_message(self, message: TopicMessage, origin: Link):
    await self.send_to(message, [ link for link in self.link_manager.links if link != origin and message.topic in link.in_topics])

  async def on_out_topics_changed(self, message: OutTopicsChangedRecvMessage, origin: Link):
    out_topics_added, out_topics_removed = self.out_topics.change_many(message.add, message.remove)
    if len(out_topics_added) > 0 or len(out_topics_removed) > 0:
      await self.send_to(OutTopicsChangedMessage(out_topics_added, out_topics_removed), [ conn for conn in self.link_manager.links if conn != origin ])

    resub_topics = set()
    for pt in message.add:
      if pt.id in self.in_topics:
        topic_provider = next((conn for conn in self.link_manager.links if pt.id in conn.recv_topics), None)
        if topic_provider is None or topic_provider.out_topics[pt.id] > pt.cost:
          resub_topics.add(pt.id)
    await self.request_in_topics_change(resub_topics, resub_topics) # resub to the better providers

  async def on_addresses_changed(self, message: AddressesChangedRecvMessage, origin: Link):
    addresses_added, addresses_removed = self.addresses.change_many(message.add, message.remove)
    if len(addresses_added) > 0 or len(addresses_removed) > 0:
      await self.send_to(AddressesChangedMessage(addresses_added, addresses_removed), [ conn for conn in self.link_manager.links if conn != origin ])

  async def handle_message(self, message: Message, origin: Link):
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
      logging.warning(f"Unhandled message {message}")

  async def _run_link_receiving(self, link: Link):
    try:
      while True:
        message = await link.recv()
        await self.handle_message(message, link)
    except asyncio.CancelledError: pass
    except ConnectionClosedError: pass
    except BaseException as e:
      logging.error(f"Error receiving from link: {e}")
      raise e
    finally:
      await self.remove_link(link)
