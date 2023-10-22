from typing import Optional
import asyncio

from streamtasks.net import Link, Switch, create_queue_connection


class Worker:
  def __init__(self, node_link: Link, switch: Optional[Switch] = None):
    self.node_link = node_link
    self.switch = switch if switch is not None else Switch()
    self.connected = asyncio.Event()

  async def create_link(self, raw: bool = False) -> Link:
    connection = create_queue_connection(raw)
    await self.switch.add_link(connection[0])
    return connection[1]

  async def start(self):
    try:
      await self.switch.add_link(self.node_link)
      self.connected.set()
      await asyncio.Future() # wait for cancellation
    finally: self.switch.stop_receiving()
