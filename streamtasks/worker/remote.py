from streamtasks.worker import Worker
from streamtasks.comm import RemoteAddress, IPCSwitch, IPCConnection, connect_to_listener
import asyncio

class RemoteServerWorker(Worker):
  bind_address: RemoteAddress
  switch: IPCSwitch

  def __init__(self, node_id: int, bind_address: RemoteAddress):
    super().__init__(node_id, IPCSwitch(bind_address))

  async def async_start(self, stop_signal: asyncio.Event):
    await asyncio.gather(
      self.switch.start_listening(stop_signal),
      super().async_start(stop_signal)
    )

class RemoteClientWorker(Worker):
  remote_address: RemoteAddress
  remote_conn: Optional[IPCConnection]
  connection_cost: int

  def __init__(self, node_id: int, remote_address: RemoteAddress, connection_cost: int = 10):
    super().__init__(node_id)
    self.remote_address = remote_address
    self.connection_cost = connection_cost
    self.remote_conn = None

  async def async_start(self, stop_signal: asyncio.Event):
    await self.connect_to_remote()
    await super().async_start(stop_signal)

  async def process(self):
    await self.connect_to_remote(stop_signal)
    await super().process()

  async def connect_to_remote(self):
    while self.remote_conn is None or self.remote_conn.closed:
      self.remote_conn = connect_to_listener(self.remote_address)
      if self.remote_conn is None: await asyncio.sleep(1)
      else: 
        self.remote_conn.cost = self.connection_cost
        await self.switch.add_connection(self.remote_conn)