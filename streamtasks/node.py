import asyncio
from streamtasks.comm import IPCSwitch, get_node_socket_path, Switch, create_local_cross_connector
from abc import ABC

class NodeBase(ABC):
  running: bool
  switch: Switch

  def __init__(self, switch: Switch):
    self.running = False
    self.switch = switch

  async def async_start(self, stop_signal: asyncio.Event):
    self.running = True
    await self._start_switching(stop_signal)
    self.running = False
    
  async def _start_switching(self, stop_signal: asyncio.Event):
    while not stop_signal.is_set():
      await self.switch.process()
      await asyncio.sleep(0.001)

class LocalNode(NodeBase):
  def __init__(self):
    super().__init__(Switch())

  async def create_connection(self):
    connector = create_local_cross_connector()
    await self.switch.add_connection(connector[0])
    return connector[1]

class IPCNode(NodeBase):
  switch: IPCSwitch

  def __init__(self, id: int):
    super().__init__(IPCSwitch(get_node_socket_path(id)))

  async def async_start(self, stop_signal: asyncio.Event):
    await asyncio.gather(
      super().async_start(stop_signal),
      self.switch.start_listening(stop_signal),
    )