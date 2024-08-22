from typing import Any
from streamtasks.client.signal import SignalServer
from streamtasks.services.constants import NetworkAddresses, NetworkTopics
from streamtasks.worker import Worker
from streamtasks.client import Client
from streamtasks.client.fetch import FetchRequest, FetchServer, new_fetch_body_bad_request, new_fetch_body_not_found
from streamtasks.net.serialization import RawData
from streamtasks.net.messages import TopicControlData
from streamtasks.client.discovery import DsicoveryConstants, AddressNameAssignmentMessage, GenerateAddressesRequestMessage, GenerateAddressesRequestMessageBase, GenerateAddressesResponseMessage, GenerateAddressesResponseMessageBase, GenerateTopicsRequestBody, GenerateTopicsResponseBody, RegisterAddressRequestBody, RegisterTopicSpaceRequestMessage, ResolveAddressRequestBody, ResolveAddressResonseBody, TopicSpaceRequestMessage, TopicSpaceResponseMessage, TopicSpaceTranslationRequestMessage, TopicSpaceTranslationResponseMessage
import logging
import asyncio

class DiscoveryWorker(Worker):
  def __init__(self):
    super().__init__()
    self._address_counter = NetworkAddresses.COUNTER_INIT
    self._topics_counter = NetworkTopics.COUNTER_INIT
    self._topic_space_id_counter = 0
    self._address_map: dict[str, int] = {}
    self._topic_spaces: dict[int, dict[int, int]] = {}

  async def run(self):
    client = await self.create_client()
    client.start()
    await client.set_address(NetworkAddresses.ID_DISCOVERY)

    try:
      async with client.out_topics_context([NetworkTopics.ADDRESSES_CREATED, NetworkTopics.DISCOVERY_SIGNAL, NetworkTopics.ADDRESS_NAME_ASSIGNED]):
        await asyncio.gather(
          self._run_address_generator(client),
          self._run_fetch_server(client),
          self._run_lighthouse(client),
        )
    finally:
      self._address_counter = NetworkAddresses.COUNTER_INIT
      self._topics_counter = NetworkTopics.COUNTER_INIT
      self._address_map = {}
      await self.shutdown()

  async def _run_lighthouse(self, client: Client):
    await client.send_stream_control(NetworkTopics.DISCOVERY_SIGNAL, TopicControlData(False)) # NOTE: not sure if i want this...
    while True:
      await client.send_stream_data(NetworkTopics.DISCOVERY_SIGNAL, RawData("running"))
      await asyncio.sleep(1)

  async def _run_fetch_server(self, client: Client):
    server = FetchServer(client)

    @server.route(DsicoveryConstants.REGISTER_ADDRESS)
    async def _(req: FetchRequest):
      request: RegisterAddressRequestBody = RegisterAddressRequestBody.model_validate(req.body)
      logging.info(f"registering address name {request.address_name} for address {request.address}")
      if request.address is None: self._address_map.pop(request.address_name, None)
      else: self._address_map[request.address_name] = request.address

      await client.send_stream_data(NetworkTopics.ADDRESS_NAME_ASSIGNED, RawData(AddressNameAssignmentMessage(
        address_name=request.address_name,
        address=self._address_map.get(request.address_name, None)
      ).model_dump()))

    @server.route(DsicoveryConstants.RESOLVE_ADDRESS)
    async def _(req: FetchRequest):
      request: ResolveAddressRequestBody = ResolveAddressRequestBody.model_validate(req.body)
      logging.info(f"resolving the address for {request.address_name}")
      await req.respond(ResolveAddressResonseBody(address=self._address_map.get(request.address_name, None)).model_dump())

    @server.route(DsicoveryConstants.REQUEST_TOPICS)
    async def _(req: FetchRequest):
      request = GenerateTopicsRequestBody.model_validate(req.body)
      logging.info(f"generating {request.count} topics")
      topics = self.generate_topic_ids(request.count)
      await req.respond(GenerateTopicsResponseBody(topics=topics).model_dump())

    @server.route(DsicoveryConstants.REQUEST_ADDRESSES)
    async def _(req: FetchRequest):
      message = GenerateAddressesRequestMessageBase.model_validate(req.body)
      logging.info(f"generating {message.count} addresses")
      addresses = self.generate_addresses(message.count)
      await req.respond(GenerateAddressesResponseMessageBase(addresses=addresses).model_dump())

    @server.route(DsicoveryConstants.REGISTER_TOPIC_SPACE)
    async def _(req: FetchRequest):
      message = RegisterTopicSpaceRequestMessage.model_validate(req.body)
      logging.info(f"generating topic space for {len(message.topic_ids)} topic ids")
      new_topic_ids = self.generate_topic_ids(len(message.topic_ids))
      self._topic_space_id_counter += 1
      topic_id_map = { k: v for k, v in zip(message.topic_ids, new_topic_ids) }
      self._topic_spaces[self._topic_space_id_counter] = topic_id_map
      await req.respond(TopicSpaceResponseMessage(id=self._topic_space_id_counter, topic_id_map=list(topic_id_map.items())).model_dump())

    @server.route(DsicoveryConstants.GET_TOPIC_SPACE_TRANSLATION)
    async def _(req: FetchRequest):
      try:
        message = TopicSpaceTranslationRequestMessage.model_validate(req.body)
        topic_id_map = self._topic_spaces[message.topic_space_id]
        await req.respond(TopicSpaceTranslationResponseMessage(topic_id=topic_id_map[message.topic_id]).model_dump())
      except KeyError as e:
        await req.respond_error(new_fetch_body_not_found(str(e)))

    @server.route(DsicoveryConstants.GET_TOPIC_SPACE)
    async def _(req: FetchRequest):
      try:
        message = TopicSpaceRequestMessage.model_validate(req.body)
        topic_id_map = self._topic_spaces[message.id]
        await req.respond(TopicSpaceResponseMessage(id=message.id, topic_id_map=list(topic_id_map.items())).model_dump())
      except KeyError as e:
        await req.respond_error(new_fetch_body_not_found(str(e)))

    @server.route(DsicoveryConstants.DELETE_TOPIC_SPACE)
    async def _(req: FetchRequest):
      try:
        request = TopicSpaceRequestMessage.model_validate(req.body)
        self._topic_spaces.pop(request.id)
        await req.respond("OK")
      except KeyError as e:
        await req.respond_error(new_fetch_body_bad_request(str(e)))

    await server.run()

  async def _run_address_generator(self, client: Client):
    signal_server = SignalServer(client)

    @signal_server.route(DsicoveryConstants.REQUEST_ADDRESSES)
    async def _(message_data: Any):
      request = GenerateAddressesRequestMessage.model_validate(message_data)
      logging.info(f"generating {request.count} addresses")
      addresses = self.generate_addresses(request.count)
      await client.send_stream_data(NetworkTopics.ADDRESSES_CREATED, RawData(GenerateAddressesResponseMessage(
        request_id=request.request_id,
        addresses=addresses
      ).model_dump()))

    await signal_server.run()

  def generate_topic_ids(self, count: int) -> set[int]:
    res = set(self._topics_counter + i for i in range(count))
    self._topics_counter += count
    return res

  def generate_addresses(self, count: int) -> set[int]:
    res = set(self._address_counter + i for i in range(count))
    self._address_counter += count
    return res
