from abc import abstractmethod
from streamtasks.client import Client
from streamtasks.net import Switch

class Worker:
  def __init__(self): self.switch = Switch()

  async def create_link(self): return await self.switch.add_local_connection()
  async def create_client(self): return Client(await self.create_link())

  @abstractmethod
  async def run(self): pass
  async def shutdown(self): self.switch.stop_receiving()
