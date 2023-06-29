from streamtasks.worker import Worker
from streamtasks.client import Client, FetchRequest
from streamtasks.protocols import *
from streamtasks.comm.serialization import JsonData, TextData, MessagePackData
from streamtasks.comm.types import TopicControlData
import logging
import asyncio

class DiscoveryWorker(Worker):
  _address_counter: int
  _topics_counter: int
  _address_map: dict[str, int]

  def __init__(self, node_id: int):
    super().__init__(node_id)
    self._address_counter = WorkerAddresses.COUNTER_INIT
    self._topics_counter = WorkerTopics.COUNTER_INIT
    self._address_map = {}

  async def async_start(self, stop_signal: asyncio.Event):
    client = Client(await self.create_connection())
    await client.change_addresses([WorkerAddresses.ID_DISCOVERY])
    await client.provide([WorkerTopics.ADDRESSES_CREATED, WorkerTopics.DISCOVERY_SIGNAL, WorkerTopics.ADDRESS_NAME_ASSIGNED])

    await asyncio.gather(
      self._run_address_generator(stop_signal, client),
      self._run_fetch_server(stop_signal, client),
      self._run_lighthouse(stop_signal, client),
      super().async_start(stop_signal)
    )

  async def _run_lighthouse(self, stop_signal: asyncio.Event, client: Client):
    await self.running.wait()
    await client.send_stream_control(WorkerTopics.DISCOVERY_SIGNAL, TopicControlData(False)) # NOTE: not sure if i want this...
    while not stop_signal.is_set():
      await client.send_stream_data(WorkerTopics.DISCOVERY_SIGNAL, TextData("running"))
      await asyncio.sleep(1)

  async def _run_fetch_server(self, stop_signal: asyncio.Event, client: Client):
    server = client.create_fetch_server()

    @server.route(WorkerFetchDescriptors.REGISTER_ADDRESS)
    async def register_address(req: FetchRequest):
      request: RegisterAddressRequestBody = RegisterAddressRequestBody.parse_obj(req.body)
      logging.info(f"registering address name {request.address_name} for address {request.address}")
      if request.address is None: self._address_map.pop(request.address_name, None)
      else: self._address_map[request.address_name] = request.address

      await client.send_stream_data(WorkerTopics.ADDRESS_NAME_ASSIGNED, MessagePackData(AddressNameAssignmentMessage(
        address_name=request.address_name,
        address=self._address_map.get(request.address_name, None)
      ).dict()))

      await req.respond(None)

    @server.route(WorkerFetchDescriptors.RESOLVE_ADDRESS)
    async def resolve_address(req: FetchRequest):
      request: ResolveAddressRequestBody = ResolveAddressRequestBody.parse_obj(req.body)
      logging.info(f"resolving the address for {request.address_name}")
      await req.respond(ResolveAddressResonseBody(address=self._address_map.get(request.address_name, None)).dict())

    @server.route(WorkerFetchDescriptors.GENERATE_TOPICS)
    async def generate_topics(req: FetchRequest):
      request = GenerateTopicsRequestBody.parse_obj(req.body)
      logging.info(f"generating {request.count} topics")
      topics = self.generate_topics(request.count)
      await req.respond(GenerateTopicsResponseBody(topics=topics).dict())

    await server.async_start(stop_signal)

  async def _run_address_generator(self, stop_signal: asyncio.Event, client: Client):
    async with client.get_address_receiver([WorkerAddresses.ID_DISCOVERY]) as receiver:
      while not stop_signal.is_set():
        try:
          if not receiver.empty():
            address, message = await receiver.recv()
            request = GenerateAddressesRequestMessage.parse_obj(message.data)
            logging.info(f"generating {request.count} addresses")
            addresses = self.generate_addresses(request.count)
            await client.send_stream_data(WorkerTopics.ADDRESSES_CREATED, JsonData(GenerateAddressesResponseMessage(
              request_id=request.request_id, 
              addresses=addresses
            ).dict()))
          else: await asyncio.sleep(0.001)
        except Exception as e: 
          logging.error(e)
  
  def generate_topics(self, count: int) -> set[int]:
    res = set(self._topics_counter + i for i in range(count))
    self._topics_counter += count
    return res

  def generate_addresses(self, count: int) -> set[int]:
    res = set(self._address_counter + i for i in range(count))
    self._address_counter += count
    return res


