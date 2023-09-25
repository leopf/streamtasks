from typing import Optional, Any
import asyncio
from streamtasks.net import *
from streamtasks.helpers import IdTracker, AwaitableIdTracker
from streamtasks.system.protocols import WorkerAddresses, WorkerFetchDescriptors
from streamtasks.message.serializers import get_core_serializers
from streamtasks.message.data import *
from streamtasks.client.receiver import *
from streamtasks.client.fetch import FetchReponseReceiver, FetchRequestMessage, FetchRequestReceiver, FetchServerReceiver
from streamtasks.client.helpers import ProvideContext, ProvideTracker, SubscibeContext, SubscribeTracker
import secrets

class Client:
  _link: Link
  _receivers:  list[Receiver]
  _receive_task: Optional[asyncio.Task]
  _addresses: set[int]
  _fetch_id_counter: int
  _address_request_lock: asyncio.Lock
  _address_map: dict[str, int]
  _custom_serializers: dict[int, Serializer]
  _subscribing_topics: IdTracker
  _provided_topics: IdTracker

  def __init__(self, link: Link):
    self._link = link
    self._receivers = []
    self._receive_task = None
    self._addresses = set()
    self._fetch_id_counter = 0
    self._address_request_lock = asyncio.Lock()
    self._address_map = {}
    self._custom_serializers = get_core_serializers()

    self._subscribed_provided_topics = AwaitableIdTracker()
    self._subscribing_topics = IdTracker()
    self._provided_topics = IdTracker()

  @property
  def default_address(self): return next(iter(self._addresses), None)

  def get_topics_receiver(self, topics: Iterable[Union[int, SubscribeTracker]], subscribe: bool = True): return TopicsReceiver(self, set(topics), subscribe)
  def get_address_receiver(self, addresses: Iterable[int]): return AddressReceiver(self, set(addresses))
  def get_fetch_request_receiver(self, descriptor: str): return FetchRequestReceiver(self, descriptor)
  def create_fetch_server(self): return FetchServerReceiver(self)
  
  def create_subscription_tracker(self): return SubscribeTracker(self)
  def create_provide_tracker(self): return ProvideTracker(self)

  def add_serializer(self, serializer: Serializer): 
    if serializer.content_id not in self._custom_serializers: self._custom_serializers[serializer.content_id] = serializer
  def remove_serializer(self, content_id: int): self._custom_serializers.pop(content_id, None)

  async def wait_for_topic_signal(self, topic: int): return await TopicSignalReceiver(self, topic).wait()
  async def wait_for_address_name(self, name: str):
    found_address = self._address_map.get(name, None)
    if found_address is not None: return found_address

    receiver = AddressNameAssignedReceiver(self)
    async with receiver:
      result = await self.resolve_address_name(name)
      if result is not None:
        self._set_address_name(name, result)
        found_address = result
      while found_address is None:
        data = await receiver.recv()
        self._set_address_name(data.address_name, data.address)
        if data.address_name == name: found_address = data.address

    while not receiver.empty():
      data: AddressNameAssignmentMessage = await receiver.get()
      self._set_address_name(data.address_name, data.address)

    return found_address

  def topic_is_subscribed(self, topic: int): return topic in self._subscribed_provided_topics
  async def wait_topic_subscribed(self, topic: int, subscribed: bool = True): 
    if (topic in self._subscribed_provided_topics) == subscribed: return
    if subscribed: return await self._subscribed_provided_topics.wait_for_id_added(topic)
    else: return await self._subscribed_provided_topics.wait_for_id_removed(topic)
  async def send_to(self, address: Union[int, str], data: Any): await self._link.send(AddressedMessage(await self._get_address(address), data))
  async def send_stream_control(self, topic: int, control_data: TopicControlData): await self._link.send(control_data.to_message(topic))
  async def send_stream_data(self, topic: int, data: SerializableData): await self._link.send(TopicDataMessage(topic, data))

  async def unregister_address_name(self, name: str): await self._register_address_name(name, None)
  async def register_address_name(self, name: str, address: Optional[int] = None): 
    address = address or self.default_address
    if address is None: raise Exception("No local address")
    await self._register_address_name(name, address)
  async def resolve_address_name(self, name: str) -> Optional[int]:
    if name in self._address_map: return self._address_map[name]
    raw_res = await self.fetch(WorkerAddresses.ID_DISCOVERY, WorkerFetchDescriptors.RESOLVE_ADDRESS, ResolveAddressRequestBody(address_name=name).model_dump())
    res: ResolveAddressResonseBody = ResolveAddressResonseBody.model_validate(raw_res)
    if res.address is not None: self._address_map[name] = res.address
    return res.address

  async def request_address(self): return next(iter(await self.request_addresses(1, apply=True)))
  async def request_addresses(self, count: int, apply: bool=False) -> set[int]:
    async with self._address_request_lock:
      request_id = secrets.randbelow(1<<64)
      async with ResolveAddressesReceiver(self, request_id) as receiver:
        await self.send_to(WorkerAddresses.ID_DISCOVERY, JsonData(GenerateAddressesRequestMessage(request_id=request_id, count=count).model_dump()))
        data: GenerateAddressesResponseMessage = await receiver.recv()
        addresses = set(data.addresses)
    
    if len(addresses) != count: raise Exception("The response returned an invalid number of addresses")
    if apply: await self.change_addresses(self._addresses | addresses)
    return addresses

  async def request_topic_ids(self, count: int, apply: bool=False) -> set[int]:
    raw_res = await self.fetch(WorkerAddresses.ID_DISCOVERY, WorkerFetchDescriptors.GENERATE_TOPICS, GenerateTopicsRequestBody(count=count).model_dump())
    res = GenerateTopicsResponseBody.model_validate(raw_res)
    if len(res.topics) != count: raise Exception("The fetch request returned an invalid number of topics")
    if apply: await self.provide(res.topics)
    return res.topics

  async def change_addresses(self, addresses: Iterable[int]):
    new_addresses = set(addresses)
    add = new_addresses - self._addresses
    remove = self._addresses - new_addresses
    await self._link.send(AddressesChangedMessage(ids_to_priced_ids(add), remove))
    self._addresses = new_addresses

  def provide_context(self, topics: Iterable[int]): return ProvideContext(self, topics)
  async def provide(self, topics: Iterable[int]):
    actually_added = self._provided_topics.add_many(topics)
    if len(actually_added) > 0: await self._link.send(OutTopicsChangedMessage(ids_to_priced_ids(actually_added), set()))
  async def unprovide(self, topics: Iterable[int]):
    actually_removed = self._provided_topics.remove_many(topics)
    if len(actually_removed) > 0: await self._link.send(OutTopicsChangedMessage(set(), set(actually_removed)))
  def subscribe_context(self, topics: Iterable[int]): return SubscibeContext(self, topics)
  async def subscribe(self, topics: Iterable[int]):
    actually_added = self._subscribing_topics.add_many(topics)
    if len(actually_added) > 0: await self._link.send(InTopicsChangedMessage(set(actually_added), set()))
  async def unsubscribe(self, topics: Iterable[int]):
    actually_removed = self._subscribing_topics.remove_many(topics)
    if len(actually_removed) > 0: await self._link.send(InTopicsChangedMessage(set(), set(actually_removed)))

  async def fetch(self, address: Union[int, str], descriptor: str, body):
    self._fetch_id_counter = fetch_id = self._fetch_id_counter + 1
    if self.default_address is None: raise Exception("No local address")
    await self.send_to(address, JsonData(FetchRequestMessage(
      return_address=self.default_address, 
      request_id=fetch_id, 
      descriptor=descriptor, 
      body=body).model_dump()))
    receiver = FetchReponseReceiver(self, fetch_id)
    response_data = await receiver.recv()
    return response_data

  async def enable_receiver(self, receiver: Receiver):
    self._receivers.append(receiver)
    self._receive_task = self._receive_task or asyncio.create_task(self._task_receive())
  async def disable_receiver(self, receiver: Receiver): 
    self._receivers.remove(receiver)
    if len(self._receivers) == 0 and self._receive_task is not None: 
      self._receive_task.cancel()
      try: await self._receive_task
      except: pass

  async def _get_address(self, address: Union[int, str]) -> int: return await self.resolve_address_name(address) if isinstance(address, str) else address
  async def _register_address_name(self, name: str, address: Optional[int]):
    await self.fetch(WorkerAddresses.ID_DISCOVERY, WorkerFetchDescriptors.REGISTER_ADDRESS, RegisterAddressRequestBody(address_name=name, address=address).model_dump())
    self._set_address_name(name, address)
  def _set_address_name(self, name: str, address: Optional[int]):
    if address is None: self._address_map.pop(name, None)
    else: self._address_map[name] = address

  async def _task_receive(self):
    try:
      while len(self._receivers) > 0:
        message = await self._link.recv()
        if isinstance(message, InTopicsChangedMessage): self._subscribed_provided_topics.change_many(message.add, message.remove)
        if isinstance(message, TopicMessage) and message.topic not in self._subscribing_topics: continue
        if isinstance(message, DataMessage) and message.data.type == SerializationType.CUSTOM: message.data.serializer = self._custom_serializers.get(message.data.content_id, None)
        for receiver in self._receivers:
          receiver.on_message(message)
    finally:
      self._receive_task = None