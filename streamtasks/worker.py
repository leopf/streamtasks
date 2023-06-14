from streamtasks.comm import *
from multiprocessing.connection import Client, Listener
from typing import Union, Optional
from enum import Enum
import asyncio
import logging
from streamtasks.client import Client, FetchRequest
from streamtasks.protocols import *

class Worker:
  node_id: int
  switch: Switch
  node_conn: Optional[IPCConnection]
  running: bool

  def __init__(self, node_id: int, switch: Optional[Switch] = None):
    self.node_id = node_id
    self.switch = switch if switch is not None else Switch()
    self.running = False
    self.node_conn = None

  def signal_stop(self): self.running = False

  def create_connection(self) -> Connection:
    connector = create_local_cross_connector()
    self.switch.add_connection(connector[0])
    return connector[1]

  async def process(self):
    await self.connect_to_node()
    self.switch.process()

  async def async_start(self):
    await self.connect_to_node()
    self.running = True
    while self.running:
      await self.process()
      await asyncio.sleep(0.001)

  async def connect_to_node(self):
    while self.node_conn is None or self.node_conn.closed:
      self.node_conn = connect_to_listener(get_node_socket_path(self.node_id))
      if self.node_conn is None: await asyncio.sleep(1)
      else: self.switch.add_connection(self.node_conn)

class DiscoveryWorker(Worker):
  _address_counter: int
  _topics_counter: int

  def __init__(self, node_id: int):
    super().__init__(node_id)
    self._address_counter = WorkerAddresses.COUNTER_INIT
    self._topics_counter = WorkerTopics.COUNTER_INIT

  async def async_start(self):
    client = Client(self.create_connection())
    client.change_addresses([WorkerAddresses.ID_DISCOVERY])

    await asyncio.gather(
      self._run_address_discorvery(client),
      super().async_start()
    )


  async def _run_topic_discovery(self, client: Client):
    with client.get_fetch_request_receiver("request_topics") as receiver:
      while self.running:
        if not receiver.empty():
          req: FetchRequest = await receiver.recv()
          if not isinstance(req.body, RequestTopicsBody): continue
          request: RequestTopicsBody = req.body
          logging.info(f"discovering {request.count} topics")
          topics = self.generate_topics(request.count)
          req.respond(ResolveTopicBody(topics))
        else:
          await asyncio.sleep(0.001)

  async def _run_address_discorvery(self, client: Client):
    with client.get_address_receiver([WorkerAddresses.ID_DISCOVERY]) as receiver:
      while self.running:
        if not receiver.empty():
          message = await receiver.recv()
          if not isinstance(message.data, RequestAddressesMessage): continue
          request: RequestAddressesMessage = message.data
          logging.info(f"discovering {request.count} addresses")
          addresses = self.generate_addresses(request.count)
          client.send_stream_data(WorkerTopics.ADDRESSES_CREATED, ResolveAddressesMessage(request.request_id, addresses))
        else:
          await asyncio.sleep(0.001)
  
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

  def signal_stop(self):
    self.switch.signal_stop()
    super().signal_stop()

  async def async_start(self):
    await asyncio.gather(
      self.switch.start_listening(),
      super().async_start()
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

  async def async_start(self):
    await self.connect_to_remote()
    await super().async_start()

  async def process(self):
    await self.connect_to_remote()
    await super().process()

  async def connect_to_remote(self):
    while self.remote_conn is None or self.remote_conn.connection.closed:
      self.remote_conn = connect_to_listener(self.remote_address)
      if self.remote_conn is None: await asyncio.sleep(1)
      else: 
        self.remote_conn.cost = self.connection_cost
        self.switch.add_connection(self.remote_conn)
