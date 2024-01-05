import unittest
from streamtasks.client.discovery import wait_for_topic_signal
from streamtasks.node import LocalNode
from streamtasks.services.protocols import WorkerAddresses, WorkerTopics
from streamtasks.worker import Worker
from streamtasks.client import Client
from streamtasks.services.discovery import DiscoveryWorker
import asyncio


@unittest.skip("not implemented")
class TestWorkers(unittest.IsolatedAsyncioTestCase):
  node: LocalNode
  worker: Worker
  tasks: list[asyncio.Task]

  async def asyncSetUp(self):
    self.tasks = []
    self.node = LocalNode()

    self.worker = Worker(await self.node.create_link(raw=True))
    await self.setup_worker(self.worker)

    self.tasks.append(asyncio.create_task(self.node.start()))

    await asyncio.sleep(0.001)

  async def wait_for(self, fut): return await asyncio.wait_for(fut, 2)

  async def asyncTearDown(self):
    for task in self.tasks:
      if task.done(): await task
      else: task.cancel()

  async def setup_worker(self, worker: Worker):
    self.tasks.append(asyncio.create_task(worker.start()))
    await asyncio.sleep(0.001) # wait for worker setup

  async def test_address_discovery(self):
    discovery_worker = DiscoveryWorker(await self.node.create_link(raw=True))
    await self.setup_worker(discovery_worker)

    client = Client(await self.worker.create_link(raw=True))

    await self.wait_for(wait_for_topic_signal(client, WorkerTopics.DISCOVERY_SIGNAL))

    own_address = await self.wait_for(client.request_address())
    self.assertEqual(WorkerAddresses.COUNTER_INIT, own_address)

    expected_addresses = list(range(WorkerAddresses.COUNTER_INIT + 1, WorkerAddresses.COUNTER_INIT + 6))
    addresses = await self.wait_for(client._request_addresses(5))
    addresses = list(addresses)

    self.assertEqual(5, len(addresses))
    self.assertEqual(expected_addresses, list(addresses))

  async def test_wait_for_name(self): # NOTE: this test is broken, waiter before is not waiting for the fetch to finish
    discovery_worker = DiscoveryWorker(await self.node.create_link(raw=True))
    await self.setup_worker(discovery_worker)

    client1 = Client(await self.worker.create_link(raw=True))
    await self.wait_for(wait_for_topic_signal(client1, WorkerTopics.DISCOVERY_SIGNAL))

    await self.wait_for(client1.request_address())
    client2 = Client(await self.worker.create_link(raw=True))
    await self.wait_for(client2.request_address())
    client3 = Client(await self.worker.create_link(raw=True))
    await self.wait_for(client3.request_address())

    async def waiter_before():
      self.assertEqual(await self.wait_for(client3.wait_for_address_name("c1")), client1.address)

    waiter_task = asyncio.create_task(waiter_before())

    await client1.register_address_name("c1")
    await asyncio.sleep(0.001)
    self.assertEqual(await self.wait_for(client2.wait_for_address_name("c1")), client1.address)
    await waiter_task

  async def test_address_name_resolver(self):
    discovery_worker = DiscoveryWorker(await self.node.create_link(raw=True))
    await self.setup_worker(discovery_worker)

    client1 = Client(await self.worker.create_link(raw=True))
    await self.wait_for(wait_for_topic_signal(client1, WorkerTopics.DISCOVERY_SIGNAL))
    await self.wait_for(client1.request_address())

    self.assertEqual(len(list(client1._in_topics.items())), 0)

    client2 = Client(await self.worker.create_link(raw=True))
    await self.wait_for(client2.request_address())

    await client1.register_address_name("c1")
    await asyncio.sleep(0.001)
    self.assertEqual(await client2.resolve_address_name("c1"), client1.address)

  async def test_topic_discovery(self):
    discovery_worker = DiscoveryWorker(await self.node.create_link(raw=True))
    await self.setup_worker(discovery_worker)

    client = Client(await self.worker.create_link(raw=True))

    await self.wait_for(wait_for_topic_signal(client, WorkerTopics.DISCOVERY_SIGNAL))

    await self.wait_for(client.request_address()) # make sure we have an address
    topics = await self.wait_for(client.request_topic_ids(5, apply=True))
    topics = list(topics)

    self.assertEqual(5, len(topics))

    expected_topics = list(range(WorkerTopics.COUNTER_INIT, WorkerTopics.COUNTER_INIT + 5))
    self.assertEqual(expected_topics, topics)
    self.assertEqual(set(expected_topics), client._out_topics.items())


if __name__ == '__main__':
  unittest.main()
