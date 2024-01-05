from typing import Iterable, Optional, Any, Union
import asyncio
from streamtasks.client.receiver import Receiver, ResolveAddressesReceiver, TopicsReceiver
from streamtasks.client.topic import InTopic, InTopicSynchronizer, OutTopic, InTopicsContext, OutTopicsContext, SynchronizedInTopic
from streamtasks.helpers import IdGenerator, IdTracker, AwaitableIdTracker
from streamtasks.message.data import MessagePackData, SerializableData, SerializationType, Serializer
from streamtasks.net import Endpoint, Link
from streamtasks.net.helpers import ids_to_priced_ids
from streamtasks.net.types import AddressedMessage, AddressesChangedMessage, DataMessage, InTopicsChangedMessage, OutTopicsChangedMessage, TopicControlData, TopicDataMessage, TopicMessage
from streamtasks.services.protocols import GenerateAddressesRequestMessage, GenerateAddressesResponseMessage, GenerateTopicsRequestBody, GenerateTopicsResponseBody, ResolveAddressRequestBody, ResolveAddressResonseBody, WorkerAddresses, WorkerFetchDescriptors, WorkerPorts
from streamtasks.message.serializers import get_core_serializers
from streamtasks.client.fetch import FetchReponseReceiver, FetchRequestMessage
import secrets


class Client:
  def __init__(self, link: Link):
    self._link = link
    self._started_event = asyncio.Event()
    self._receivers: list[Receiver] = []
    self._receive_task: Optional[asyncio.Task] = None
    self._address: Optional[int] = None
    self._address_resolver_cache: dict[str, int] = {}
    self._custom_serializers = get_core_serializers()
    self._port_generator = IdGenerator(WorkerPorts.DYNAMIC_START, 0xffffffffffffffff)

    self._subscribed_provided_topics = AwaitableIdTracker()
    self._in_topics = IdTracker()
    self._out_topics = IdTracker()

  @property
  def address(self): return self._address

  def get_topics_receiver(self, topics: Iterable[int], subscribe: bool = True): return TopicsReceiver(self, set(topics), subscribe)
  def out_topic(self, topic: int): return OutTopic(self, topic)
  def in_topic(self, topic: int): return InTopic(self, topic)
  def sync_in_topic(self, topic: int, sync: InTopicSynchronizer): return SynchronizedInTopic(self, topic, sync)

  def start(self): self._started_event.set()
  def stop(self): self._started_event.clear()

  def add_serializer(self, serializer: Serializer):
    if serializer.content_id not in self._custom_serializers: self._custom_serializers[serializer.content_id] = serializer
  def remove_serializer(self, content_id: int): self._custom_serializers.pop(content_id, None)

  def get_free_port(self): return self._port_generator.next()

  async def send_to(self, endpoint: Endpoint, data: SerializableData):
    await self._link.send(AddressedMessage(
      await self._get_address(endpoint[0]),
      endpoint[1],
      data
    ))
  async def send_stream_control(self, topic: int, control_data: TopicControlData): await self._link.send(control_data.to_message(topic))
  async def send_stream_data(self, topic: int, data: SerializableData): await self._link.send(TopicDataMessage(topic, data))
  async def resolve_address_name(self, name: str) -> Optional[int]:
    if name in self._address_resolver_cache: return self._address_resolver_cache[name]
    raw_res = await self.fetch(WorkerAddresses.ID_DISCOVERY, WorkerFetchDescriptors.RESOLVE_ADDRESS, ResolveAddressRequestBody(address_name=name).model_dump())
    res: ResolveAddressResonseBody = ResolveAddressResonseBody.model_validate(raw_res)
    if res.address is not None: self._address_resolver_cache[name] = res.address
    return res.address

  async def request_address(self):
    addresses = await self._request_addresses(1)
    new_address = next(iter(addresses))
    assert self._address is None, "there cant be an address already present, when requesting one"
    await self.set_address(new_address)
    return new_address

  async def request_topic_ids(self, count: int, apply: bool = False) -> set[int]:
    raw_res = await self.fetch(WorkerAddresses.ID_DISCOVERY, WorkerFetchDescriptors.GENERATE_TOPICS, GenerateTopicsRequestBody(count=count).model_dump())
    res = GenerateTopicsResponseBody.model_validate(raw_res)
    if len(res.topics) != count: raise Exception("The fetch request returned an invalid number of topics")
    if apply: await self.register_out_topics(res.topics)
    return res.topics

  async def set_address(self, address: Optional[int]):
    new_addresses = set() if address is None else set([ address ])
    old_addresses = set() if self._address is None else set([ self._address ])
    add = new_addresses - old_addresses
    remove = old_addresses - new_addresses
    if len(add) > 0 or len(remove) > 0:
      await self._link.send(AddressesChangedMessage(ids_to_priced_ids(add), remove))
    self._address = address

  def out_topics_context(self, topics: Iterable[int]): return OutTopicsContext(self, topics)
  def in_topics_context(self, topics: Iterable[int]): return InTopicsContext(self, topics)

  async def register_out_topics(self, topics: Iterable[int]):
    actually_added = self._out_topics.add_many(topics)
    if len(actually_added) > 0: await self._link.send(OutTopicsChangedMessage(ids_to_priced_ids(actually_added), set()))
  async def unregister_out_topics(self, topics: Iterable[int], force: bool = False):
    actually_removed = self._out_topics.remove_many(topics, force=force)
    if len(actually_removed) > 0: await self._link.send(OutTopicsChangedMessage(set(), set(actually_removed)))
  async def register_in_topics(self, topics: Iterable[int]):
    actually_added = self._in_topics.add_many(topics)
    if len(actually_added) > 0: await self._link.send(InTopicsChangedMessage(set(actually_added), set()))
  async def unregister_in_topics(self, topics: Iterable[int], force: bool = False):
    actually_removed = self._in_topics.remove_many(topics, force=force)
    if len(actually_removed) > 0: await self._link.send(InTopicsChangedMessage(set(), set(actually_removed)))

  async def fetch(self, address: str | int, descriptor: str, body: Any, port=WorkerPorts.FETCH):
    if self.address is None: raise Exception("No local address")
    return_port = self.get_free_port()
    async with FetchReponseReceiver(self, return_port) as receiver:
      await self.send_to((address, port), MessagePackData(FetchRequestMessage(
        return_address=self.address,
        return_port=return_port,
        descriptor=descriptor,
        body=body).model_dump()))
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
      except asyncio.CancelledError: pass

  def set_address_name(self, name: str, address: Optional[int]):
    if address is None: self._address_resolver_cache.pop(name, None)
    else: self._address_resolver_cache[name] = address

  async def _request_addresses(self, count: int) -> set[int]:
    request_id = secrets.randbelow(1 << 64)
    async with ResolveAddressesReceiver(self, request_id) as receiver:
      await self.send_to(
        (WorkerAddresses.ID_DISCOVERY, WorkerPorts.DISCOVERY_REQUEST_ADDRESS),
        MessagePackData(GenerateAddressesRequestMessage(request_id=request_id, count=count).model_dump()))
      data: GenerateAddressesResponseMessage = await receiver.recv()
      addresses = set(data.addresses)
    if len(addresses) != count: raise Exception("The response returned an invalid number of addresses")
    return addresses
  async def _get_address(self, address: Union[int, str]) -> int: return await self.resolve_address_name(address) if isinstance(address, str) else address

  async def _task_receive(self):
    try:
      while len(self._receivers) > 0:
        await self._started_event.wait()
        message = await self._link.recv()
        await self._started_event.wait()
        if isinstance(message, InTopicsChangedMessage): self._subscribed_provided_topics.change_many(message.add, message.remove)
        if isinstance(message, TopicMessage) and message.topic not in self._in_topics: continue
        if isinstance(message, DataMessage) and message.data.type == SerializationType.CUSTOM: message.data.serializer = self._custom_serializers.get(message.data.content_id, None)
        for receiver in self._receivers:
          receiver.on_message(message)
    finally:
      self._receive_task = None