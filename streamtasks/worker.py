from streamtasks.comm import *
from multiprocessing.connection import Client, Listener
from typing import Union, Optional
from enum import Enum
import asyncio
import logging
from streamtasks.client import Client, FetchRequest
from streamtasks.protocols import *
from streamtasks.comm.serialization import *

class Worker:
  node_id: int
  switch: Switch
  node_conn: Optional[Connection]
  running: bool

  def __init__(self, node_id: int, switch: Optional[Switch] = None):
    self.node_id = node_id
    self.switch = switch if switch is not None else Switch()
    self.running = False
    self.node_conn = None

  async def set_node_connection(self, conn: Connection):
    if self.node_conn is not None: await self.switch.remove_connection(self.node_conn)
    self.node_conn = conn
    await self.switch.add_connection(conn)

  async def create_connection(self, raw: bool = False) -> Connection:
    connector = create_local_cross_connector(raw)
    await self.switch.add_connection(connector[0])
    return connector[1]

  async def process(self):
    await self.connect_to_node()
    await self.switch.process()

  async def async_start(self, stop_signal: asyncio.Event):
    await self.connect_to_node()
    self.running = True
    while not stop_signal.is_set():
      await self.process()
      await asyncio.sleep(0.001)
    self.running = False

  async def connect_to_node(self):
    while self.node_conn is None or self.node_conn.closed:
      conn = connect_to_listener(get_node_socket_path(self.node_id))
      if conn is None: await asyncio.sleep(1)
      else: await self.set_node_connection(conn)

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
    await client.provide([WorkerTopics.ADDRESSES_CREATED])

    await asyncio.gather(
      self._run_address_generator(stop_signal, client),
      self._run_topic_generator(stop_signal, client),
      self._run_address_name_resolver(stop_signal, client),
      self._run_address_name_registry(stop_signal, client),
      super().async_start(stop_signal)
    )

  async def _run_address_name_registry(self, stop_signal: asyncio.Event, client: Client):
    with client.get_fetch_request_receiver(WorkerFetchDescriptors.REGISTER_ADDRESS) as receiver:
      while not stop_signal.is_set():
        try:
          if not receiver.empty():
            req: FetchRequest = await receiver.recv()
            request: RegisterAddressRequestBody = RegisterAddressRequestBody.parse_obj(req.body)
            logging.info(f"registering address name {request.address_name} for address {request.address}")
            if request.address is None: self._address_map.pop(request.address_name, None)
            else: self._address_map[request.address_name] = request.address
            await req.respond(None) # any response signifies success
          else: await asyncio.sleep(0.001)
        except Exception as e: logging.error(e)

  async def _run_address_name_resolver(self, stop_signal: asyncio.Event, client: Client):
    with client.get_fetch_request_receiver(WorkerFetchDescriptors.RESOLVE_ADDRESS) as receiver:
      while not stop_signal.is_set():
        try:
          if not receiver.empty():
            req: FetchRequest = await receiver.recv()
            request: ResolveAddressRequestBody = ResolveAddressRequestBody.parse_obj(req.body)
            logging.info(f"resolving the address for {request.address_name}")
            await req.respond(ResolveAddressResonseBody(address=self._address_map.get(request.address_name, None)).dict())
          else: await asyncio.sleep(0.001)
        except Exception as e: logging.error(e)

  async def _run_topic_generator(self, stop_signal: asyncio.Event, client: Client):
    with client.get_fetch_request_receiver(WorkerFetchDescriptors.GENERATE_TOPICS) as receiver:
      while not stop_signal.is_set():
        try:
          if not receiver.empty():
            req: FetchRequest = await receiver.recv()
            request = GenerateTopicsRequestBody.parse_obj(req.body)
            logging.info(f"generating {request.count} topics")
            topics = self.generate_topics(request.count)
            await req.respond(GenerateTopicsResponseBody(topics=topics).dict())
          else: await asyncio.sleep(0.001)
        except Exception as e: logging.error(e)

  async def _run_address_generator(self, stop_signal: asyncio.Event, client: Client):
    with client.get_address_receiver([WorkerAddresses.ID_DISCOVERY]) as receiver:
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

class RemoteServerWorker(Worker):
  bind_address: RemoteAddress
  switch: IPCSwitch

  def __init__(self, node_id: int, bind_address: RemoteAddress):
    super().__init__(node_id, IPCSwitch(bind_address))

  async def async_start(self, stop_signal: asyncio.Event):
    await asyncio.gather(
      self.switch.start_listening(stop_signal),
      super().async_start(stop_signal)
    )

class RemoteClientWorker(Worker):
  remote_address: RemoteAddress
  remote_conn: Optional[IPCConnection]
  connection_cost: int

  def __init__(self, node_id: int, remote_address: RemoteAddress, connection_cost: int = 10):
    super().__init__(node_id)
    self.remote_address = remote_address
    self.connection_cost = connection_cost
    self.remote_conn = None

  async def async_start(self, stop_signal: asyncio.Event):
    await self.connect_to_remote()
    await super().async_start(stop_signal)

  async def process(self):
    await self.connect_to_remote(stop_signal)
    await super().process()

  async def connect_to_remote(self):
    while self.remote_conn is None or self.remote_conn.closed:
      self.remote_conn = connect_to_listener(self.remote_address)
      if self.remote_conn is None: await asyncio.sleep(1)
      else: 
        self.remote_conn.cost = self.connection_cost
        await self.switch.add_connection(self.remote_conn)
