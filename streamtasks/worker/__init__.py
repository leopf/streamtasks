from streamtasks.comm import *
from typing import Optional
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

