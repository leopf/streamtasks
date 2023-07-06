import asyncio
from streamtasks.comm import IPCSwitch, get_node_socket_path, Switch, create_local_cross_connector
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
      self.switch.close_all_connections()
      self.running = False

class LocalNode(NodeBase):
  def __init__(self):
    super().__init__(Switch())

  async def create_connection(self, raw: bool = False):
    connector = create_local_cross_connector(raw)
    await self.switch.add_connection(connector[0])
    return connector[1]

class IPCNode(NodeBase):
  switch: IPCSwitch

  def __init__(self, id: int):
    super().__init__(IPCSwitch(get_node_socket_path(id)))

  async def start(self):
    await asyncio.gather(
      super().start(),
      self.switch.start_listening(),
    )