from streamtasks.comm import *
from multiprocessing.connection import Client, Listener
from typing import Union, Optional
import asyncio
import logging

class Worker:
  node_id: int
  switch: TopicSwitch
  node_conn: Optional[IPCTopicConnection]
  running: bool

  def __init__(self, node_id: int, switch: Optional[TopicSwitch] = None):
    self.node_id = node_id
    self.switch = switch if switch is not None else TopicSwitch()
    self.running = False

  def signal_stop(self): self.running = False

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
      self.node_conn = connect_to_listener(get_node_socket_path(self.node_id))
      if self.node_conn is None: await asyncio.sleep(1)

class RemoteServerWorker(Worker):
  bind_address: RemoteAddress
  switch: IPCTopicSwitch

  def __init__(self, node_id: int, bind_address: RemoteAddress):
    super().__init__(node_id, IPCTopicSwitch(bind_address))

  def signal_stop(self):
    self.switch.signal_stop()
    super().signal_stop()

  async def async_start(self):
    await asyncio.gather(
      await self.switch.start_listening(),
      await super().async_start()
    )

class RemoteClientWorker(Worker):
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
      self.remote_conn = connect_to_listener(self.remote_address)
      if self.remote_conn is None: await asyncio.sleep(1)
