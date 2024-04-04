from abc import abstractmethod
from typing import Optional
from streamtasks.client import Client
from streamtasks.net import Link, Switch, create_queue_connection
import asyncio


class Worker:
  def __init__(self, node_link: Link, switch: Optional[Switch] = None):
    self.node_link = node_link
    self.switch = switch if switch is not None else Switch()
    self.connected = asyncio.Event()

  async def create_client(self) -> Client: return Client(await self.create_link())
  async def create_link(self) -> Link:
    connection = create_queue_connection()
    await self.switch.add_link(connection[0])
    return connection[1]

  @abstractmethod
  async def run(self): pass

  async def setup(self):
    await self.switch.add_link(self.node_link)
    self.connected.set()
    
  async def shutdown(self):
    self.switch.stop_receiving()