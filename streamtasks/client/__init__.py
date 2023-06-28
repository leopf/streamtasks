from typing import Optional, Any
import asyncio
from streamtasks.comm import *
from streamtasks.protocols import *
from streamtasks.comm.serialization import *
from streamtasks.client.receiver import *
from streamtasks.client.fetch import *
import secrets

class Client:
  _connection: Connection
  _receivers:  list[Receiver]
  _receive_task: Optional[asyncio.Task]
  _subscribed_topics: set[int]
  _provided_topics: set[int]
  _addresses: set[int]
  _fetch_id_counter: int
  _address_request_lock: asyncio.Lock
  _address_map: dict[str, int]

  def __init__(self, connection: Connection):
    self._connection = connection
    self._receivers = []
    self._receive_task = None
    self._subscribed_topics = set()
    self._provided_topics = set()
    self._addresses = set()
    self._fetch_id_counter = 0
    self._address_request_lock = asyncio.Lock()
    self._address_map = {}

  @property
  def default_address(self): return next(iter(self._addresses), None)

  def get_topics_receiver(self, topics: Iterable[int]): return TopicsReceiver(self, set(topics))
  def get_address_receiver(self, addresses: Iterable[int]): return AddressReceiver(self, set(addresses))
  def get_fetch_request_receiver(self, descriptor: str): return FetchRequestReceiver(self, descriptor)
  
  async def wait_for_topic_signal(self, topic: int): return await TopicSignalReceiver(self, topic).wait()
  async def wait_for_address_name(self, name: str):
    found_address = self._address_map.get(name, None)
    if found_address is not None: return found_address

    receiver = AddressNameAssignedReceiver(self)
    
    await self.subscribe(self._subscribed_topics | {WorkerTopics.ADDRESS_NAME_ASSIGNED})
    with receiver:
      result = await self.resolve_address_name(name)
      if result is not None:
        self._set_address_name(name, result)
        found_address = result
    await self.subscribe(self._subscribed_topics - {WorkerTopics.ADDRESS_NAME_ASSIGNED})

    while not receiver.empty():
      data: AddressNameAssignmentMessage = await receiver.get()
      self._set_address_name(data.address_name, data.address)
      if found_address is None and data.address_name == name: found_address = data.address

    return found_address

  async def send_to(self, address: Union[int, str], data: Any): await self._connection.send(AddressedMessage(await self._get_address(address), data))
  async def send_stream_control(self, topic: int, control_data: TopicControlData): await self._connection.send(control_data.to_message(topic))
  async def send_stream_data(self, topic: int, data: SerializableData): await self._connection.send(TopicDataMessage(topic, data))

  async def unregister_address_name(self, name: str): await self._register_address_name(name, None)
  async def register_address_name(self, name: str, address: Optional[int] = None): 
    address = address or self.default_address
    if address is None: raise Exception("No local address")
    await self._register_address_name(name, address)
  async def resolve_address_name(self, name: str) -> Optional[int]:
    if name in self._address_map: return self._address_map[name]
    raw_res = await self.fetch(WorkerAddresses.ID_DISCOVERY, WorkerFetchDescriptors.RESOLVE_ADDRESS, ResolveAddressRequestBody(address_name=name).dict())
    res: ResolveAddressResonseBody = ResolveAddressResonseBody.parse_obj(raw_res)
    if res.address is not None: self._address_map[name] = res.address
    return res.address

  async def request_address(self): return next(iter(await self.request_addresses(1, apply=True)))
  async def request_addresses(self, count: int, apply: bool=False) -> set[int]:
    async with self._address_request_lock:
      try:
        await self.subscribe(self._subscribed_topics | {WorkerTopics.ADDRESSES_CREATED})
        request_id = secrets.randbelow(1<<64)
        with ResolveAddressesReceiver(self, request_id) as receiver:
          await self.send_to(WorkerAddresses.ID_DISCOVERY, JsonData(GenerateAddressesRequestMessage(request_id=request_id, count=count).dict()))
          data: GenerateAddressesResponseMessage = await receiver.recv()
          addresses = set(data.addresses)
        assert len(addresses) == count, "The response returned an invalid number of addresses"
        if apply: await self.change_addresses(self._addresses | addresses)
      finally: 
        await self.subscribe(self._subscribed_topics - {WorkerTopics.ADDRESSES_CREATED})
      return addresses

  async def request_topic_ids(self, count: int, apply: bool=False) -> set[int]:
    raw_res = await self.fetch(WorkerAddresses.ID_DISCOVERY, WorkerFetchDescriptors.GENERATE_TOPICS, GenerateTopicsRequestBody(count=count).dict())
    res = GenerateTopicsResponseBody.parse_obj(raw_res)
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

  async def fetch(self, address: Union[int, str], descriptor: str, body):
    self._fetch_id_counter = fetch_id = self._fetch_id_counter + 1
    if self.default_address is None: raise Exception("No local address")
    await self.send_to(address, JsonData(FetchRequestMessage(
      return_address=self.default_address, 
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

  async def _get_address(self, address: Union[int, str]) -> int: return await self.resolve_address_name(address) if isinstance(address, str) else address
  async def _register_address_name(self, name: str, address: Optional[int]):
    await self.fetch(WorkerAddresses.ID_DISCOVERY, WorkerFetchDescriptors.REGISTER_ADDRESS, RegisterAddressRequestBody(address_name=name, address=address).dict())
    self._set_address_name(name, address)
  def _set_address_name(self, name: str, address: Optional[int]):
    if address is None: self._address_map.pop(name, None)
    else: self._address_map[name] = address

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