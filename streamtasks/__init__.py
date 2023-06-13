from typing import Union, Optional, Any, Callable, Awaitable
import multiprocessing.connection as mpconn
from abc import ABC, abstractmethod, abstractstaticmethod
from dataclasses import dataclass
from typing_extensions import Self
import asyncio
from streamtasks.comm import *
import os 
import logging
import weakref

class Node:
  id: int
  switch: IPCSwitch
  running: bool

  def __init__(self, id: int):
    self.id = id
    self.switch = IPCSwitch(get_node_socket_path(self.id))
    self.running = False

  def signal_stop(self):
    self.switch.signal_stop()
    self.running = False

  async def async_start(self):
    self.running = True
    await asyncio.gather(
      self.switch.start_listening(),
      self._start_switching()
    )

  async def _start_switching(self):
    while self.running:
      self.switch.process()
      await asyncio.sleep(0.001)

class Receiver(ABC):
  _client: weakref.ref['Client']
  _receiving: bool

  def __init__(self, client: 'Client'):
    self._recv_queue = asyncio.Queue()
    self._client = weakref.ref(client)
    self._receiving = False
  
  def start_recv(self): 
    if self._receiving: return
    self._receiving = True
    self._get_client().enable_receiver(self)

  def stop_recv(self): 
    if not self._receiving: return
    self._receiving = False
    self._get_client().disable_receiver(self)

  def __enter__(self):
    self.start_recv()
    return self
  def __exit__(self, *args):
    self.stop_recv()
    return False

  @abstractmethod
  def on_message(self, message: Message):
    pass

  async def recv(self) -> Any:
    with self:
      return await self._recv_queue.get()

  def _get_client(self) -> 'Client':
    c = self._client()
    if not c: raise Exception('Client is dead')
    return c

class AddressReceiver(Receiver):
  _addresses: set[int]

  def __init__(self, client: 'Client', addresses: set[int]):
    super().__init__(client)
    self._addresses = addresses

  def on_message(self, message: Message):
    if isinstance(message, AddressedMessage) and message.address in self._addresses:
      a_message: AddressedMessage = message
      self._recv_queue.put_nowait((a_message.address, a_message.data))

class TopicsReceiver(Receiver):
  _topics: set[int]
  _control_data: dict[int, StreamControlData]
  _recv_queue: asyncio.Queue[tuple[int, Optional[Any], Optional[StreamControlData]]]

  def __init__(self, client: 'Client', topics: set[int]):
    super().__init__(client)
    self._topics = topics
    self._control_data = None

  def on_message(self, message: Message):
    if isinstance(message, StreamDataMessage) and message.topic in self._topics:
      sd_message: StreamDataMessage = message
      if sd_message.topic in self._topics:
        self._recv_queue.put_nowait((sd_message.topic, sd_message.data, None))
    elif isinstance(message, StreamControlMessage):
      sc_message: StreamControlMessage = message
      if sc_message.topic in self._topics:
        self._control_data[sc_message.topic] = control_data = sc_message.to_data()
        self._recv_queue.put_nowait((sc_message.topic, None, control_data))

class FetchReponseReceiver(Receiver):
  _fetch_id: int
  _recv_queue: asyncio.Queue[Any]

  def __init__(self, client: 'Client', fetch_id: int):
    super().__init__(client)
    self._fetch_id = fetch_id

  def on_message(self, message: Message):
    if isinstance(message, AddressedMessage):
      a_message: AddressedMessage = message
      if isinstance(a_message.data, FetchResponseMessage):
        fr_message: FetchResponseMessage = a_message.data
        if fr_message.request_id == self._fetch_id:
          self._recv_queue.put_nowait(message.data)

class FetchRequest:
  data: Any
  _client: 'Client'
  _return_address: int
  _request_id: int

  def __init__(self, client: 'Client', return_address: int, request_id: int, data: Any):
    self._client = client
    self._return_address = return_address
    self._request_id = request_id
    self.data = data

  def respond(self, data: Any):
    self._client.send_to(self._return_address, FetchResponseMessage(self._request_id, data))

class FetchRequestReceiver(Receiver):
  _descriptor: str
  _recv_queue: asyncio.Queue[FetchRequest]

  def __init__(self, client: 'Client', descriptor: str):
    super().__init__(client)
    self._descriptor = descriptor

  def on_message(self, message: Message):
    if isinstance(message, AddressedMessage):
      a_message: AddressedMessage = message
      if isinstance(a_message.data, FetchRequestMessage):
        fr_message: FetchRequestMessage = a_message.data
        if fr_message.descriptor == self._descriptor:
          self._recv_queue.put_nowait(FetchRequest(self._get_client(), fr_message.return_address, fr_message.request_id, fr_message.data))

class Client:
  _connection: Connection
  _receivers:  list[Receiver]
  _receive_task: Optional[asyncio.Task]
  _subscribed_topics: set[int]
  _provided_topics: set[int]
  _addresses: set[int]
  _fetch_id_counter: int

  def __init__(self, connection: Connection):
    self._connection = connection
    self._receivers = []
    self._receive_task = None
    self._subscribed_topics = set()
    self._provided_topics = set()
    self._addresses = set()
    self._fetch_id_counter = 0

  def get_topics_receiver(self, topics: Iterable[int]): return TopicsReceiver(self, set(topics))
  def get_address_receiver(self, addresses: Iterable[int]): return AddressReceiver(self, set(addresses))
  def get_fetch_request_receiver(self, descriptor: str): return FetchRequestReceiver(self, descriptor)

  def send_to(self, address: int, data: Any): self._connection.send(AddressedMessage(address, data))
  def send_stream_control(self, topic: int, control_data: StreamControlData): self._connection.send(control_data.to_message(topic))
  def send_stream_data(self, topic: int, data: Any): self._connection.send(StreamDataMessage(topic, data))

  def change_addresses(self, addresses: Iterable[int]):
    new_addresses = set(addresses)
    add = new_addresses - self._addresses
    remove = self._addresses - new_addresses
    self._connection.send(AddressesChangedMessage(ids_to_priced_ids(add), remove))
    self._addresses = new_addresses

  def provide(self, topics: Iterable[int]):
    new_provided = set(topics)
    add = new_provided - self._provided_topics
    remove = self._provided_topics - new_provided
    self._connection.send(OutTopicsChangedMessage(ids_to_priced_ids(add), remove))

  async def fetch(self, address, descriptor, data):
    self._fetch_id_counter += 1
    self.send_to(address, FetchRequestMessage(self._addresses[0], self._fetch_id_counter, descriptor, data))
    receiver = FetchReponseReceiver(self, self._fetch_id_counter)
    response_data = await receiver.recv()
    return response_data

  def subscribe(self, topics: Iterable[int]):
    new_sub = set(topics)
    add = new_sub - self._subscribed_topics
    remove = self._subscribed_topics - new_sub
    self._subscribed_topics = new_sub
    self._connection.send(InTopicsChangedMessage(add, remove))

  def enable_receiver(self, receiver: Receiver):
    self._receivers.append(receiver)
    self._receive_task = self._receive_task or asyncio.create_task(self._task_receive())
  def disable_receiver(self, receiver: Receiver): self._receivers.remove(receiver)

  async def _task_receive(self):
    while len(self._receivers) > 0:
      message = self._connection.recv()
      if message:
        if isinstance(message, StreamMessage) and message.topic not in self._subscribed_topics: continue
        for receiver in self._receivers:
          receiver.on_message(message)
      await asyncio.sleep(0.001)
    self._receive_task = None
