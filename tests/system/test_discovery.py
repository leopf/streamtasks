import unittest
from streamtasks.client.discovery import register_address_name, wait_for_address_name, wait_for_topic_signal
from streamtasks.net import Switch, create_queue_connection
from streamtasks.node import LocalNode
from streamtasks.services.protocols import WorkerAddresses, WorkerTopics
from streamtasks.worker import Worker
from streamtasks.client import Client
from streamtasks.services.discovery import DiscoveryWorker
import asyncio

from tests.shared import async_timeout


# @unittest.skip("not implemented")
class TestWorkers(unittest.IsolatedAsyncioTestCase):
  node: LocalNode
  worker: Worker
  tasks: list[asyncio.Task]

  async def asyncSetUp(self):
    self.tasks = []
    self.switch = Switch()
    self.discovery_worker = DiscoveryWorker(await self.create_link())
    self.tasks.append(asyncio.create_task(self.discovery_worker.run()))
    await asyncio.sleep(0.001)

  async def create_link(self):
    conn = create_queue_connection()
    await self.switch.add_link(conn[0])
    return conn[1]
  
  async def create_client(self):
    client = Client(await self.create_link())
    client.start()
    return client

  async def asyncTearDown(self):
    self.switch.stop_receiving()
    for task in self.tasks: task.cancel()
    for task in self.tasks: 
      try: await task
      except asyncio.CancelledError: pass
      except: raise

  @async_timeout(1)
  async def test_address_discovery(self):
    client = await self.create_client()
    await wait_for_topic_signal(client, WorkerTopics.DISCOVERY_SIGNAL)

    own_address = await client.request_address()
    self.assertEqual(WorkerAddresses.COUNTER_INIT, own_address)

    expected_addresses = list(range(WorkerAddresses.COUNTER_INIT + 1, WorkerAddresses.COUNTER_INIT + 6))
    addresses = await client._request_addresses(5)
    addresses = list(addresses)

    self.assertEqual(5, len(addresses))
    self.assertEqual(expected_addresses, list(addresses))

  @async_timeout(1)
  async def test_wait_for_name(self): # NOTE: this test is broken, waiter before is not waiting for the fetch to finish
    client1 = await self.create_client()
    await wait_for_topic_signal(client1, WorkerTopics.DISCOVERY_SIGNAL)

    await client1.request_address()
    client2 = await self.create_client()
    await client2.request_address()
    client3 = await self.create_client()
    await client3.request_address()

    async def waiter_before():
      self.assertEqual(await wait_for_address_name(client3, "c1"), client1.address)

    waiter_task = asyncio.create_task(waiter_before())

    await register_address_name(client1, "c1", client1.address)
    await asyncio.sleep(0.001)
    self.assertEqual(await wait_for_address_name(client2, "c1"), client1.address)
    await waiter_task

  @async_timeout(1)
  async def test_address_name_resolver(self):
    client1 = await self.create_client()
    await wait_for_topic_signal(client1, WorkerTopics.DISCOVERY_SIGNAL)
    await client1.request_address()

    self.assertEqual(len(list(client1._in_topics.items())), 0)

    client2 = await self.create_client()
    await client2.request_address()

    await register_address_name(client1, "c1", client1.address)
    await asyncio.sleep(0.001)
    self.assertEqual(await client2.resolve_address_name("c1"), client1.address)

  @async_timeout(1)
  async def test_topic_discovery(self):
    client = await self.create_client()

    await wait_for_topic_signal(client, WorkerTopics.DISCOVERY_SIGNAL)

    await client.request_address() # make sure we have an address
    topics = await client.request_topic_ids(5, apply=True)
    topics = list(topics)

    self.assertEqual(5, len(topics))

    expected_topics = list(range(WorkerTopics.COUNTER_INIT, WorkerTopics.COUNTER_INIT + 5))
    self.assertEqual(expected_topics, topics)
    self.assertEqual(set(expected_topics), client._out_topics.items())


if __name__ == '__main__':
  unittest.main()
