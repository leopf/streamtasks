import unittest
from streamtasks.comm import *
from streamtasks.client import *
from streamtasks.worker import *
from streamtasks.node import *
import asyncio


class TestWorkers(unittest.IsolatedAsyncioTestCase):
  node: LocalNode
  worker: Worker

  stop_signal: asyncio.Event
  tasks: list[asyncio.Task]

  async def asyncSetUp(self):
    self.stop_signal = asyncio.Event()
    self.tasks = []
    self.node = LocalNode()

    self.worker = Worker(1)
    await self.setup_worker(self.worker)

    self.tasks.append(asyncio.create_task(self.node.async_start(self.stop_signal)))
    self.tasks.append(asyncio.create_task(self.worker.async_start(self.stop_signal)))

    await asyncio.sleep(0.001)

  async def asyncTearDown(self):
    self.stop_signal.set()
    for task in self.tasks: await task

  async def setup_worker(self, worker: Worker):
    await worker.set_node_connection(await self.node.create_connection(raw=True))
    self.tasks.append(asyncio.create_task(worker.async_start(self.stop_signal)))

  async def test_address_discovery(self):
    discovery_worker = DiscoveryWorker(1)
    await self.setup_worker(discovery_worker)
    await asyncio.sleep(0.001)

    client = Client(await self.worker.create_connection(raw=True))

    own_address = await asyncio.wait_for(client.request_address(), 10000) 
    self.assertEqual(WorkerAddresses.COUNTER_INIT, own_address)

    expected_addresses = list(range(WorkerAddresses.COUNTER_INIT + 1, WorkerAddresses.COUNTER_INIT + 6))
    addresses = await asyncio.wait_for(client.request_addresses(5), 1000)
    addresses = list(addresses)

    self.assertEqual(5, len(addresses))
    self.assertEqual(expected_addresses, list(addresses))

  async def test_topic_discovery(self):
    discovery_worker = DiscoveryWorker(1)
    await self.setup_worker(discovery_worker)

    client = Client(await self.worker.create_connection(raw=True))

    await asyncio.wait_for(client.request_address(), 1) # make sure we have an address
    topics = await asyncio.wait_for(client.request_topic_ids(5, apply=True), 1)
    topics = list(topics)

    self.assertEqual(5, len(topics))

    expected_topics = list(range(WorkerTopics.COUNTER_INIT, WorkerTopics.COUNTER_INIT + 5))
    self.assertEqual(expected_topics, topics)
    self.assertEqual(set(expected_topics), client._provided_topics)

if __name__ == '__main__':
  unittest.main()
