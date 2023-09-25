import asyncio
from streamtasks.net import Switch, create_queue_connection
from abc import ABC

class NodeBase(ABC):
  running: bool
  switch: Switch

  def __init__(self, switch: Switch):
    self.running = False
    self.switch = switch

  async def start(self):
    try:
      self.running = True
      await asyncio.Future() # wait for cancellation
    finally:
      self.switch.stop_receiving()
      self.running = False

class LocalNode(NodeBase):
  def __init__(self):
    super().__init__(Switch())

  async def create_link(self, raw: bool = False):
    connection = create_queue_connection(raw)
    await self.switch.add_link(connection[0])
    return connection[1]
