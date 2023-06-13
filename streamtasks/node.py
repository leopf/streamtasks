import asyncio
from streamtasks.comm import IPCSwitch, get_node_socket_path

class Node:
  id: int
  switch: IPCSwitch
  running: bool

  def __init__(self, id: int):
    self.id = id
    self.switch = IPCSwitch(get_node_socket_path(self.id))
    self.running = False

  def signal_stop(self):
    self.switch.signal_stop()
    self.running = False

  async def async_start(self):
    self.running = True
    await asyncio.gather(
      self.switch.start_listening(),
      self._start_switching()
    )

  async def _start_switching(self):
    while self.running:
      self.switch.process()
      await asyncio.sleep(0.001)
