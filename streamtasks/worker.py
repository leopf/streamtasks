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
  node_conn: Optional[Connection]
  running: bool

  def __init__(self, node_id: int, switch: Optional[Switch] = None):
    self.node_id = node_id
    self.switch = switch if switch is not None else Switch()
    self.running = False
    self.node_conn = None

  def set_node_connection(self, conn: Connection):
    if self.node_conn is not None: self.switch.remove_connection(self.node_conn)
    self.node_conn = conn
    self.switch.add_connection(conn)

  def create_connection(self) -> Connection:
    connector = create_local_cross_connector()
    self.switch.add_connection(connector[0])
    return connector[1]

  async def process(self):
    await self.connect_to_node()
    self.switch.process()

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
      else: self.set_node_connection(conn)

class DiscoveryWorker(Worker):
  _address_counter: int
  _topics_counter: int

  def __init__(self, node_id: int):
    super().__init__(node_id)
    self._address_counter = WorkerAddresses.COUNTER_INIT
    self._topics_counter = WorkerTopics.COUNTER_INIT

  async def async_start(self, stop_signal: asyncio.Event):
    client = Client(self.create_connection())
    client.change_addresses([WorkerAddresses.ID_DISCOVERY])
    client.provide([WorkerTopics.ADDRESSES_CREATED])

    await asyncio.gather(
      self._run_address_discorvery(stop_signal, client),
      self._run_topic_discovery(stop_signal, client),
      super().async_start(stop_signal)
    )


  async def _run_topic_discovery(self, stop_signal: asyncio.Event, client: Client):
    with client.get_fetch_request_receiver("request_topics") as receiver:
      while not stop_signal.is_set():
        if not receiver.empty():
          req: FetchRequest = await receiver.recv()
          if not isinstance(req.body, RequestTopicsBody): continue
          request: RequestTopicsBody = req.body
          logging.info(f"discovering {request.count} topics")
          topics = self.generate_topics(request.count)
          req.respond(ResolveTopicBody(topics))
        else:
          await asyncio.sleep(0.001)

  async def _run_address_discorvery(self, stop_signal: asyncio.Event, client: Client):
    with client.get_address_receiver([WorkerAddresses.ID_DISCOVERY]) as receiver:
      while not stop_signal.is_set():
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
        self.switch.add_connection(self.remote_conn)
