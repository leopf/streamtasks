from streamtasks.worker import Worker
from streamtasks.client import Client
from streamtasks.protocols import *
import asyncio


class TaskManagerWorker(Worker):
  ready: asyncio.Event

  def __init__(self, node_id: int):
    super().__init__(node_id)
    self.ready = asyncio.Event()

  async def async_start(self, stop_signal: asyncio.Event):
    client = Client(await self.create_connection())

    await asyncio.gather(
      self._setup(client),
      self._run_dashboard(stop_signal, client),
      super().async_start(stop_signal)
    )

  async def _setup(self, client: Client):
    await self.running.wait()
    await client.wait_for_topic_signal(WorkerTopics.DISCOVERY_SIGNAL)
    await client.request_address()
    await client.register_address_name(AddressNames.TASK_MANAGER)
    self.ready.set()


  async def _run_dashboard(self, stop_signal: asyncio.Event, client: Client):
    await self.running.wait()
    await client.send_stream_control(WorkerTopics.DISCOVERY_SIGNAL, TopicControlData(False))