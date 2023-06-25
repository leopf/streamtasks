from typing import Union, Optional, Any, Callable, Awaitable
from abc import ABC, abstractmethod
from dataclasses import dataclass
import asyncio
from streamtasks.comm import *
from streamtasks.protocols import *
from streamtasks.comm.serialization import *
import weakref
import secrets

class Receiver(ABC):
  _client: 'Client'
  _receiving_count: int

  def __init__(self, client: 'Client'):
    self._recv_queue = asyncio.Queue()
    self._client = client
    self._receiving_count = 0
  
  def start_recv(self):
    self._receiving_count += 1 
    if self._receiving_count > 1: return
    self._client.enable_receiver(self)

  def stop_recv(self): 
    self._receiving_count = max(0, self._receiving_count - 1)
    if self._receiving_count > 0: return
    self._client.disable_receiver(self)

  def __enter__(self):
    self.start_recv()
    return self
  def __exit__(self, *args):
    self.stop_recv()
    return False

  @abstractmethod
  def on_message(self, message: Message):
    pass

  def empty(self): return self._recv_queue.empty()

  async def recv(self) -> Any:
    with self:
      return await self._recv_queue.get()

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
  _control_data: dict[int, TopicControlData]
  _recv_queue: asyncio.Queue[tuple[int, Optional[Any], Optional[TopicControlData]]]

  def __init__(self, client: 'Client', topics: set[int]):
    super().__init__(client)
    self._topics = topics
    self._control_data = {}
    
  def get_control_data(self, topic: int): return self._control_data.get(topic, None)

  def on_message(self, message: Message):
    if isinstance(message, TopicDataMessage) and message.topic in self._topics:
      sd_message: TopicDataMessage = message
      if sd_message.topic in self._topics:
        self._recv_queue.put_nowait((sd_message.topic, sd_message.data, None))
    elif isinstance(message, TopicControlMessage):
      sc_message: TopicControlMessage = message
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
      if isinstance(a_message.data, JsonData):
        try:
          fr_message = FetchResponseMessage.parse_obj(a_message.data.data)
          if fr_message.request_id == self._fetch_id:
            self._recv_queue.put_nowait(fr_message.body)
        except: pass
class FetchRequest:
  body: Any
  _client: 'Client'
  _return_address: int
  _request_id: int

  def __init__(self, client: 'Client', return_address: int, request_id: int, body: Any):
    self._client = client
    self._return_address = return_address
    self._request_id = request_id
    self.body = body

  async def respond(self, body: Any):
    await self._client.send_to(self._return_address, JsonData(FetchResponseMessage(request_id=self._request_id, body=body).dict()))

class FetchRequestReceiver(Receiver):
  _descriptor: str
  _recv_queue: asyncio.Queue[FetchRequest]

  def __init__(self, client: 'Client', descriptor: str):
    super().__init__(client)
    self._descriptor = descriptor

  def on_message(self, message: Message):
    if isinstance(message, AddressedMessage):
      a_message: AddressedMessage = message
      if isinstance(a_message.data, JsonData):
        try:
          fr_message = FetchRequestMessage.parse_obj(a_message.data.data)
          if fr_message.descriptor == self._descriptor:
            self._recv_queue.put_nowait(FetchRequest(self._client, fr_message.return_address, fr_message.request_id, fr_message.body))
        except: pass
class ResolveAddressesReceiver(Receiver):
  _recv_queue: asyncio.Queue[ResolveAddressesMessage]
  _request_id: int

  def __init__(self, client: 'Client', request_id: int):
    super().__init__(client)
    self._request_id = request_id

  def on_message(self, message: Message):
    if isinstance(message, TopicDataMessage) and message.topic == WorkerTopics.ADDRESSES_CREATED:
      sd_message: TopicDataMessage = message
      if isinstance(sd_message.data, JsonData):
        try:
          ra_message = ResolveAddressesMessage.parse_obj(sd_message.data.data)
          if ra_message.request_id == self._request_id:
            self._recv_queue.put_nowait(ra_message)
        except: pass
class Client:
  _connection: Connection
  _receivers:  list[Receiver]
  _receive_task: Optional[asyncio.Task]
  _subscribed_topics: set[int]
  _provided_topics: set[int]
  _addresses: set[int]
  _fetch_id_counter: int
  _address_request_lock: asyncio.Lock

  def __init__(self, connection: Connection):
    self._connection = connection
    self._receivers = []
    self._receive_task = None
    self._subscribed_topics = set()
    self._provided_topics = set()
    self._addresses = set()
    self._fetch_id_counter = 0
    self._address_request_lock = asyncio.Lock()

  def get_topics_receiver(self, topics: Iterable[int]): return TopicsReceiver(self, set(topics))
  def get_address_receiver(self, addresses: Iterable[int]): return AddressReceiver(self, set(addresses))
  def get_fetch_request_receiver(self, descriptor: str): return FetchRequestReceiver(self, descriptor)

  async def send_to(self, address: int, data: Any): await self._connection.send(AddressedMessage(address, data))
  async def send_stream_control(self, topic: int, control_data: TopicControlData): await self._connection.send(control_data.to_message(topic))
  async def send_stream_data(self, topic: int, data: Any): await self._connection.send(TopicDataMessage(topic, data))

  async def request_address(self): return next(iter(await self.request_addresses(1, apply=True)))
  async def request_addresses(self, count: int, apply: bool=False) -> set[int]:
    async with self._address_request_lock:
      try:
        await self.subscribe(self._subscribed_topics | {WorkerTopics.ADDRESSES_CREATED})
        request_id = secrets.randbelow(1<<64)
        with ResolveAddressesReceiver(self, request_id) as receiver:
          await self.send_to(WorkerAddresses.ID_DISCOVERY, JsonData(RequestAddressesMessage(request_id=request_id, count=count).dict()))
          data: ResolveAddressesMessage = await receiver.recv()
          addresses = set(data.addresses)
        assert len(addresses) == count, "The response returned an invalid number of addresses"
        if apply: await self.change_addresses(self._addresses | addresses)
      finally: 
        await self.subscribe(self._subscribed_topics - {WorkerTopics.ADDRESSES_CREATED})
      return addresses

  async def request_topic_ids(self, count: int, apply: bool=False) -> set[int]:
    raw_res = await self.fetch(WorkerAddresses.ID_DISCOVERY, WorkerFetchDescriptors.REQUEST_TOPICS, RequestTopicsBody(count=count).dict())
    res = ResolveTopicBody.parse_obj(raw_res)
    assert len(res.topics) == count, "The fetch request returned an invalid number of topics"
    if apply: await self.provide(self._provided_topics | set(res.topics))
    return res.topics

  async def change_addresses(self, addresses: Iterable[int]):
    new_addresses = set(addresses)
    add = new_addresses - self._addresses
    remove = self._addresses - new_addresses
    await self._connection.send(AddressesChangedMessage(ids_to_priced_ids(add), remove))
    self._addresses = new_addresses

  async def provide(self, topics: Iterable[int]):
    new_provided = set(topics)
    add = new_provided - self._provided_topics
    remove = self._provided_topics - new_provided
    await self._connection.send(OutTopicsChangedMessage(ids_to_priced_ids(add), remove))
    self._provided_topics = new_provided

  async def subscribe(self, topics: Iterable[int]):
    new_sub = set(topics)
    add = new_sub - self._subscribed_topics
    remove = self._subscribed_topics - new_sub
    self._subscribed_topics = new_sub
    await self._connection.send(InTopicsChangedMessage(add, remove))

  async def fetch(self, address, descriptor, body):
    self._fetch_id_counter = fetch_id = self._fetch_id_counter + 1
    local_address = next(iter(self._addresses), None)
    if local_address is None: raise Exception("No local address")
    await self.send_to(address, JsonData(FetchRequestMessage(
      return_address=local_address, 
      request_id=fetch_id, 
      descriptor=descriptor, 
      body=body).dict()))
    receiver = FetchReponseReceiver(self, fetch_id)
    response_data = await receiver.recv()
    return response_data

  def enable_receiver(self, receiver: Receiver):
    self._receivers.append(receiver)
    self._receive_task = self._receive_task or asyncio.create_task(self._task_receive())
  def disable_receiver(self, receiver: Receiver): self._receivers.remove(receiver)

  async def _task_receive(self):
    while len(self._receivers) > 0:
      message = await self._connection.recv()
      if message:
        if isinstance(message, TopicMessage) and message.topic not in self._subscribed_topics: continue
        for receiver in self._receivers:
          receiver.on_message(message)
      else:
        await asyncio.sleep(0.001)
    self._receive_task = None