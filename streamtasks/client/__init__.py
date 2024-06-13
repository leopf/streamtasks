from typing import Iterable, Optional, Any, Union
import asyncio
from streamtasks.client.discovery import request_addresses
from streamtasks.client.receiver import Receiver, TopicsReceiver as TopicsReceiver
from streamtasks.client.topic import InTopic, InTopicSynchronizer, OutTopic, InTopicsContext, OutTopicsContext, SynchronizedInTopic
from streamtasks.utils import IdGenerator, IdTracker, AwaitableIdTracker
from streamtasks.net.serialization import RawData
from streamtasks.net import Endpoint, EndpointOrAddress, Link, endpoint_or_address_to_endpoint
from streamtasks.net.helpers import ids_to_priced_ids
from streamtasks.net.messages import AddressedMessage, AddressesChangedMessage, InTopicsChangedMessage, OutTopicsChangedMessage, TopicControlData, TopicDataMessage, TopicMessage
from streamtasks.services.protocols import GenerateTopicsRequestBody, GenerateTopicsResponseBody, ResolveAddressRequestBody, ResolveAddressResonseBody, WorkerAddresses, WorkerRequestDescriptors, WorkerPorts
from streamtasks.client.fetch import FetchError, FetchReponseReceiver, FetchRequestMessage, FetchResponseMessage


class Client:
  def __init__(self, link: Link):
    self._link = link
    self._started_event = asyncio.Event()
    self._receivers: list[Receiver] = []
    self._receive_task: Optional[asyncio.Task] = None
    self._address: Optional[int] = None
    self._address_resolver_cache: dict[str, int] = {}
    self._port_generator = IdGenerator(WorkerPorts.DYNAMIC_START, 0xffffffffffffffff)

    self._subscribed_provided_topics = AwaitableIdTracker()
    self._in_topics = IdTracker()
    self._out_topics = IdTracker()

  @property
  def address(self): return self._address

  def out_topic(self, topic: int): return OutTopic(self, topic)
  def in_topic(self, topic: int): return InTopic(self, topic)
  def sync_in_topic(self, topic: int, sync: InTopicSynchronizer): return SynchronizedInTopic(self, topic, sync)

  def start(self): self._started_event.set()
  async def stop_wait(self):
    self._started_event.clear()
    if self._receive_task is not None:
      self._receive_task.cancel("stopped receiving!")
      try: await self._receive_task
      except asyncio.CancelledError: pass

  def get_free_port(self): return self._port_generator.next()

  async def send_to(self, endpoint: Endpoint, data: RawData):
    await self._link.send(AddressedMessage(
      await self._get_address(endpoint[0]),
      endpoint[1],
      data
    ))
  async def send_stream_control(self, topic: int, control_data: TopicControlData): await self._link.send(control_data.to_message(topic))
  async def send_stream_data(self, topic: int, data: RawData): await self._link.send(TopicDataMessage(topic, data))
  async def resolve_address_name(self, name: str) -> Optional[int]:
    if name in self._address_resolver_cache: return self._address_resolver_cache[name]
    raw_res = await self.fetch(WorkerAddresses.ID_DISCOVERY, WorkerRequestDescriptors.RESOLVE_ADDRESS, ResolveAddressRequestBody(address_name=name).model_dump())
    res: ResolveAddressResonseBody = ResolveAddressResonseBody.model_validate(raw_res)
    if res.address is not None: self._address_resolver_cache[name] = res.address
    return res.address

  async def request_address(self):
    addresses = await request_addresses(self, 1)
    new_address = next(iter(addresses))
    assert self._address is None, "there cant be an address already present, when requesting one"
    await self.set_address(new_address)
    return new_address

  async def request_topic_ids(self, count: int, apply: bool = False) -> set[int]:
    raw_res = await self.fetch(WorkerAddresses.ID_DISCOVERY, WorkerRequestDescriptors.REQUEST_TOPICS, GenerateTopicsRequestBody(count=count).model_dump())
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

  async def fetch(self, endpoint: EndpointOrAddress, descriptor: str, body: Any):
    if self.address is None: raise Exception("No local address")
    return_port = self.get_free_port()
    async with FetchReponseReceiver(self, return_port) as receiver:
      await self.send_to(endpoint_or_address_to_endpoint(endpoint, WorkerPorts.FETCH), RawData(FetchRequestMessage(
        return_address=self.address,
        return_port=return_port,
        descriptor=descriptor,
        body=body).model_dump()))
      response_data: FetchResponseMessage = await receiver.get()
    if response_data.error:
      raise FetchError(response_data.body)
    return response_data.body

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

  async def _get_address(self, address: Union[int, str]) -> int: return await self.resolve_address_name(address) if isinstance(address, str) else address

  async def _task_receive(self):
    try:
      while len(self._receivers) > 0:
        await self._started_event.wait()
        message = await self._link.recv()
        await self._started_event.wait()
        if isinstance(message, InTopicsChangedMessage): self._subscribed_provided_topics.change_many(message.add, message.remove)
        if isinstance(message, TopicMessage) and message.topic not in self._in_topics: continue
        for receiver in self._receivers:
          receiver.on_message(message)
    finally:
      self._receive_task = None
