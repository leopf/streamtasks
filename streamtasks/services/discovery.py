from typing import Any
from streamtasks.client.receiver import AddressReceiver
from streamtasks.client.signal import SignalRequestReceiver

# NOTE: move this in here?
from streamtasks.services.protocols import AddressNameAssignmentMessage, GenerateAddressesRequestMessage, GenerateAddressesRequestMessageBase, GenerateAddressesResponseMessage, GenerateAddressesResponseMessageBase, GenerateTopicsRequestBody, GenerateTopicsResponseBody, RegisterAddressRequestBody, ResolveAddressRequestBody, ResolveAddressResonseBody, WorkerAddresses, WorkerRequestDescriptors, WorkerPorts, WorkerTopics

from streamtasks.worker import Worker
from streamtasks.client import Client
from streamtasks.client.fetch import FetchRequest, FetchServer
from streamtasks.net.message.data import SerializableData, TextData, MessagePackData
from streamtasks.net.message.types import TopicControlData
from streamtasks.net import Link
import pydantic
import logging
import asyncio


class DiscoveryWorker(Worker):
  def __init__(self, node_link: Link):
    super().__init__(node_link)
    self._address_counter = WorkerAddresses.COUNTER_INIT
    self._topics_counter = WorkerTopics.COUNTER_INIT
    self._address_map: dict[str, int] = {}

  async def run(self):
    await self.setup()
    client = await self.create_client()
    client.start()
    await client.set_address(WorkerAddresses.ID_DISCOVERY)

    try:
      async with client.out_topics_context([WorkerTopics.ADDRESSES_CREATED, WorkerTopics.DISCOVERY_SIGNAL, WorkerTopics.ADDRESS_NAME_ASSIGNED]):
        await asyncio.gather(
          self._run_address_generator(client),
          self._run_fetch_server(client),
          self._run_lighthouse(client),
        )
    finally:
      self._address_counter = WorkerAddresses.COUNTER_INIT
      self._topics_counter = WorkerTopics.COUNTER_INIT
      self._address_map = {}
      await self.shutdown()

  async def _run_lighthouse(self, client: Client):
    await self.connected.wait()
    await client.send_stream_control(WorkerTopics.DISCOVERY_SIGNAL, TopicControlData(False)) # NOTE: not sure if i want this...
    while True:
      await client.send_stream_data(WorkerTopics.DISCOVERY_SIGNAL, TextData("running"))
      await asyncio.sleep(1)

  async def _run_fetch_server(self, client: Client):
    server = FetchServer(client)

    @server.route(WorkerRequestDescriptors.REGISTER_ADDRESS)
    async def _(req: FetchRequest):
      request: RegisterAddressRequestBody = RegisterAddressRequestBody.model_validate(req.body)
      logging.info(f"registering address name {request.address_name} for address {request.address}")
      if request.address is None: self._address_map.pop(request.address_name, None)
      else: self._address_map[request.address_name] = request.address

      await client.send_stream_data(WorkerTopics.ADDRESS_NAME_ASSIGNED, MessagePackData(AddressNameAssignmentMessage(
        address_name=request.address_name,
        address=self._address_map.get(request.address_name, None)
      ).model_dump()))

    @server.route(WorkerRequestDescriptors.RESOLVE_ADDRESS)
    async def _(req: FetchRequest):
      request: ResolveAddressRequestBody = ResolveAddressRequestBody.model_validate(req.body)
      logging.info(f"resolving the address for {request.address_name}")
      await req.respond(ResolveAddressResonseBody(address=self._address_map.get(request.address_name, None)).model_dump())

    @server.route(WorkerRequestDescriptors.REQUEST_TOPICS)
    async def _(req: FetchRequest):
      request = GenerateTopicsRequestBody.model_validate(req.body)
      logging.info(f"generating {request.count} topics")
      topics = self.generate_topics(request.count)
      await req.respond(GenerateTopicsResponseBody(topics=topics).model_dump())
      
    @server.route(WorkerRequestDescriptors.REQUEST_ADDRESSES)
    async def _(req: FetchRequest):
      request = GenerateAddressesRequestMessageBase.model_validate(req.body)
      logging.info(f"generating {request.count} addresses")
      addresses = self.generate_addresses(request.count)
      await req.respond(GenerateAddressesResponseMessageBase(addresses=addresses).model_dump())

    await server.run()

  async def _run_address_generator(self, client: Client):
    async with SignalRequestReceiver(client, WorkerRequestDescriptors.REQUEST_ADDRESSES) as receiver:
      while True:
        try:
          message_data: Any = await receiver.recv()
          request = GenerateAddressesRequestMessage.model_validate(message_data)
          logging.info(f"generating {request.count} addresses")
          addresses = self.generate_addresses(request.count)
          await client.send_stream_data(WorkerTopics.ADDRESSES_CREATED, MessagePackData(GenerateAddressesResponseMessage(
            request_id=request.request_id,
            addresses=addresses
          ).model_dump()))
        except pydantic.ValidationError: pass
        except Exception as e: logging.error(e)

  def generate_topics(self, count: int) -> set[int]:
    res = set(self._topics_counter + i for i in range(count))
    self._topics_counter += count
    return res

  def generate_addresses(self, count: int) -> set[int]:
    res = set(self._address_counter + i for i in range(count))
    self._address_counter += count
    return res