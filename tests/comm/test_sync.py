import asyncio
import random
import unittest

from streamtasks.client import Client
from streamtasks.client.topic import InTopic, InTopicSynchronizer, SequentialInTopicSynchronizer
from streamtasks.net import ConnectionClosedError, Switch, create_queue_connection
from streamtasks.net.message.data import RawData
from streamtasks.message import NumberMessage
from streamtasks.utils import get_timestamp_ms


class TestSync(unittest.IsolatedAsyncioTestCase):
  topic_count = 3
  message_count = 100

  async def asyncSetUp(self):
    self.tasks: list[asyncio.Task] = []
    conn1 = create_queue_connection(raw=False)
    conn2 = create_queue_connection(raw=True)
    self.switch = Switch()
    await self.switch.add_link(conn1[0])
    await self.switch.add_link(conn2[0])
    self.a = Client(conn1[1])
    self.a.start()
    self.b = Client(conn2[1])
    self.b.start()

  async def asyncTearDown(self):
    for task in self.tasks: task.cancel()
    for task in self.tasks:
      try: await task
      except (asyncio.CancelledError, ConnectionClosedError): pass
      except: raise
    self.switch.stop_receiving()

  async def test_seq_sync(self): await self._test_sync(SequentialInTopicSynchronizer(), self.message_count - self.topic_count)

  async def _test_sync(self, sync: InTopicSynchronizer, expected_count: int):
    self.assertGreater(expected_count, 0, "you must expect at least 1 message or the test is pointless...")
    sync = SequentialInTopicSynchronizer()
    in_topics = [ self.b.sync_in_topic(i, sync) for i in range(1, self.topic_count + 1) ]
    recv_queue = asyncio.Queue[float]()

    async def run_in_topic(topic: InTopic):
      async with topic, topic.RegisterContext():
        while True:
          data = await topic.recv_data()
          message = NumberMessage.model_validate(data.data)
          await recv_queue.put(message.value)

    out_topics = [ self.a.out_topic(i) for i in range(1, self.topic_count + 1) ]
    for out_topic in out_topics:
      await out_topic.start()
      await out_topic.set_registered(True)

    self.tasks.extend(asyncio.create_task(run_in_topic(in_topic)) for in_topic in in_topics)
    for out_topic in out_topics:
      await out_topic.wait_requested()

    rng = random.Random(42)
    start_time = get_timestamp_ms() # for realtime based syncs
    random_count = self.message_count - self.topic_count # we need this to make the expected messages deterministic
    for i in range(random_count):
      topic = rng.choice(out_topics)
      await topic.send(RawData(NumberMessage(timestamp=i + start_time, value=i).model_dump()))

    for i, topic in enumerate(out_topics):
      await topic.send(RawData(NumberMessage(timestamp=random_count + i + start_time, value=i).model_dump()))

    for i in range(expected_count):
      v = await recv_queue.get()
      self.assertEqual(i, v)

if __name__ == '__main__':
  unittest.main()
