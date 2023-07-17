from streamtasks.comm import *
from typing import Optional
import asyncio
from streamtasks.message.data import *

class Worker:
  switch: Switch
  connected: asyncio.Event

  def __init__(self, node_connection: Connection, switch: Optional[Switch] = None):
    self.node_connection = node_connection
    self.switch = switch if switch is not None else Switch()
    self.connected = asyncio.Event()

  async def create_connection(self, raw: bool = False) -> Connection:
    connector = create_local_cross_connector(raw)
    await self.switch.add_connection(connector[0])
    return connector[1]

  async def start(self):
    try:
      await self.switch.add_connection(self.node_connection)
      self.connected.set()
      await asyncio.Future() # wait for cancellation
    finally: self.switch.close_all_connections()
