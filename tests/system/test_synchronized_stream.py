import unittest
from streamtasks.comm import Switch, create_local_cross_connector
from streamtasks.client import Client
from streamtasks.streams import StreamSynchronizer, SynchronizedStream
from streamtasks.message import StringMessage, JsonData
import asyncio


class TestSynchronizedStream(unittest.IsolatedAsyncioTestCase):
  a: Client
  b: Client
  tasks: list[asyncio.Task]
  
  async def asyncSetUp(self):
    conn1 = create_local_cross_connector(raw=False)
    conn2 = create_local_cross_connector(raw=True)

    self.switch = Switch()
    await self.switch.add_connection(conn1[0])
    await self.switch.add_connection(conn2[0])

    self.tasks = []
    
    self.timestamp = 0
    self.a = Client(conn1[1])
    self.b = Client(conn2[1])

    await asyncio.sleep(0.001)

  async def asyncTearDown(self):
    self.switch.close_all_connections()
    for task in self.tasks: task.cancel()

  async def send_text(self, topic: int, text: str):
    self.timestamp += 1
    await self.a.send_stream_data(topic, JsonData(StringMessage(timestamp=self.timestamp, value=text).dict()))

  async def test_synchronized_stream(self):
    async with self.a.provide_context([ 1, 2 ]):
      sync = StreamSynchronizer()
      stream1 = SynchronizedStream(sync, self.b.get_topics_receiver([ 1 ]))
      stream2 = SynchronizedStream(sync, self.b.get_topics_receiver([ 2 ]))

      await stream1.receiver.start_recv()
      await stream2.receiver.start_recv()

      expected_values = [
        "a ", "a 1", "b 1", "c 1", "c 2", "d 2", "e 2", "f 2", "f 3"
      ]
      current_value_1 = ""
      current_value_2 = ""

      await self.send_text(1, "a")
      await self.send_text(2, "1")
      await self.send_text(1, "b")
      await self.send_text(1, "c")
      await self.send_text(2, "2")
      await self.send_text(1, "d")
      await self.send_text(1, "e")
      await self.send_text(1, "f")
      await self.send_text(2, "3")
      await self.send_text(1, "g")

      while len(expected_values) > 0:
        recv1_task = asyncio.create_task(stream1.recv())
        recv2_task = asyncio.create_task(stream2.recv())
        await asyncio.wait([ recv1_task, recv2_task ], return_when=asyncio.FIRST_COMPLETED)

        if recv1_task.done():
          with recv1_task.result() as message:
            if message.data is not None: current_value_1 = message.data.data["value"]
            if message.control is not None: current_value_1 = ("p" if message.control.paused else "u") +  current_value_1
        if recv2_task.done():
          with recv2_task.result() as message:
            if message.data is not None: current_value_2 = message.data.data["value"]
            if message.control is not None: current_value_2 = ("p" if message.control.paused else "u") +  current_value_2

        value = current_value_1 + " " + current_value_2
        self.assertEqual(value, expected_values.pop(0))

if __name__ == '__main__':
  unittest.main()