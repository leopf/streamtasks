import asyncio
from streamtasks.comm import IPCSwitch, get_node_socket_path, Switch, create_local_cross_connector
from abc import ABC

class NodeBase(ABC):
  running: bool
  switch: Switch

  def __init__(self, switch: Switch):
    self.running = False
    self.switch = switch

  def signal_stop(self):
    self.running = False

  async def async_start(self):
    self.running = True
    await self._start_switching()
    
  async def _start_switching(self):
    while self.running:
      self.switch.process()
      await asyncio.sleep(0.001)

class LocalNode(NodeBase):
  def __init__(self):
    super().__init__(Switch())

  def create_connection(self):
    connector = create_local_cross_connector()
    self.switch.add_connection(connector[0])
    return connector[1]

class IPCNode(NodeBase):
  switch: IPCSwitch

  def __init__(self, id: int):
    super().__init__(IPCSwitch(get_node_socket_path(id)))

  def signal_stop(self):
    super().signal_stop()
    self.switch.signal_stop()

  async def async_start(self):
    await asyncio.gather(
      super().async_start(),
      self.switch.start_listening(),
    )