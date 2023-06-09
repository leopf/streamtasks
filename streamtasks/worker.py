from streamtasks.comm import *
from multiprocessing.connection import Client
from typing import Union, Optional
import asyncio
import logging

class Worker:
  node_id: int
  switch: TopicSwitch
  node_conn: Optional[IPCTopicConnection]
  running: bool

  def __init__(self, node_id: int):
    self.node_id = node_id
    self.switch = TopicSwitch()
    self.running = False

  def signal_stop(self):
    self.running = False

  def create_connection(self) -> TopicConnection:
    connector = create_local_cross_connector()
    self.switch.add_connection(connector[0])
    return connector[1]

  def start(self):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(self.async_start())

  async def process(self):
    await self.connect_to_node()
    self.switch.process()

  async def async_start(self):
    await self.connect_to_node()
    self.running = True
    while self.running:
      await self.process()
      await asyncio.sleep(0)

  async def connect_to_node(self):
    while self.node_conn is None or self.node_conn.connection.closed:
      logging.info(f"Connecting to node {self.node_id}")

      try:
        self.node_conn = IPCTopicConnection(Client(get_node_socket_path(self.node_id)))
        self.switch.add_connection(self.node_conn)
        logging.info(f"Connected to node {self.node_id}")
      except ConnectionRefusedError:
        logging.info(f"Connection to node {self.node_id} refused")
        await asyncio.sleep(1)

    
RemoteAddress = Union[str, tuple[str, int]]

class RemoteConnectionWorker(Worker):
  remote_address: RemoteAddress
  remote_conn: Optional[IPCTopicConnection]

  def __init__(self, node_id: int, remote_address: RemoteAddress):
    super().__init__(node_id)
    self.remote_address = remote_address

  async def async_start(self):
    await self.connect_to_remote()
    await super().async_start()

  async def process(self):
    await self.connect_to_remote()
    await super().process()

  async def connect_to_remote(self):
    while self.remote_conn is None or self.remote_conn.connection.closed:
      logging.info(f"Connecting to remote {self.remote_address}")
      try:
        self.remote_conn = IPCTopicConnection(Client(self.remote_address))
        self.switch.add_connection(self.remote_conn)
        logging.info(f"Connected to remote {self.remote_address}")
      except ConnectionRefusedError:
        logging.info(f"Connection to remote {self.remote_address} refused")
        await asyncio.sleep(1)
