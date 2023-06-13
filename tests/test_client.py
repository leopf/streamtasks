import unittest
from streamtasks.comm import *
from streamtasks.types import *
from streamtasks import Client

class TestClient(unittest.IsolatedAsyncioTestCase):
  a: Client
  b: Client
  stop_switch_event: asyncio.Event
  
  async def asyncSetUp(self):
    conn1 = create_local_cross_connector()
    conn2 = create_local_cross_connector()

    switch = Switch()
    switch.add_connection(conn1[0])
    switch.add_connection(conn2[0])

    switch_process_task, switch_process_stop_event = create_switch_processing_task(switch)
    self.stop_switch_event = switch_process_stop_event
    
    self.a = Client(conn1[1])
    self.b = Client(conn2[1])

  async def asyncTearDown(self):
    self.stop_switch_event.set()

  async def test_provide_subscribe(self):
    self.a.provide([ 1, 2 ])
    self.b.subscribe([ 1, 2 ])

    b_recv = self.b.get_topics_receiver([ 1, 2 ])
    self.a.send_stream_data(1, "Hello 1")
    self.a.send_stream_data(2, "Hello 2")

    self.assertEqual(await b_recv.recv(), (1, "Hello 1", None))
    self.assertEqual(await b_recv.recv(), (2, "Hello 2", None))

    self.b.subscribe([ 2 ])

    self.a.send_stream_data(1, "Hello 1")
    self.a.send_stream_data(2, "Hello 2")

    rv = await b_recv.recv()
    self.assertEqual(rv, (2, "Hello 2", None))

  async def test_address(self):
    self.a.change_addresses([1])
    a_recv = self.a.get_address_receiver([1])

    yield # allow switch to process address change

    self.b.send_to(1, "Hello 1")

    self.assertEqual(await a_recv.recv(), (1, "Hello 1"))
if __name__ == '__main__':
  unittest.main()
