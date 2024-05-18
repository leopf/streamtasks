from abc import abstractmethod
from streamtasks.client import Client
from streamtasks.net import Link, Switch, create_queue_connection

class Worker:
  def __init__(self, link: Link):
    self.link = link
    self.switch = Switch()

  async def create_client(self) -> Client: return Client(await self.create_link())
  async def create_link(self) -> Link:
    connection = create_queue_connection()
    await self.switch.add_link(connection[0])
    return connection[1]

  @abstractmethod
  async def run(self): pass
  async def setup(self): await self.switch.add_link(self.link)
  async def shutdown(self): self.switch.stop_receiving()
