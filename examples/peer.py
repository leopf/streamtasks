import logging
import os
logging.basicConfig(level=logging.INFO)
os.environ["DATA_DIR"] = ".data"

import functools
import asyncio
from streamtasks.client import Client
from streamtasks.client.discovery import wait_for_topic_signal
from streamtasks.net import Switch
from streamtasks.services.protocols import AddressNames, WorkerTopics
from streamtasks.system.helpers import get_all_task_hosts
from streamtasks.worker import Worker
from streamtasks.connection import AutoReconnector, connect, connect_node, get_server
import argparse

parser = argparse.ArgumentParser(description="Argument parser for connect and serve URLs")
parser.add_argument("--connect", help="Specify URL to connect to", default=None)
parser.add_argument("--serve", help="Specify URL to serve on", default=None)
args = parser.parse_args()

async def main():
  switch = Switch()
  client = Client(await switch.add_local_connection())
  client.start()
  
  connection = AutoReconnector(await switch.add_local_connection(), connect_node if args.connect is None else functools.partial(connect, url=args.connect))
  connection_task = asyncio.create_task(connection.run())
  await wait_for_topic_signal(client, WorkerTopics.DISCOVERY_SIGNAL)
  logging.info("Connected to main!")
  
  workers: list[Worker] = []
  if args.serve is not None: workers.append(get_server(await switch.add_local_connection(), args.serve))
  
  for TaskHostCls in get_all_task_hosts(): workers.append(TaskHostCls(await switch.add_local_connection(), register_endpoits=[AddressNames.TASK_MANAGER]))
  done_tasks, _ = await asyncio.wait([connection_task] + [ asyncio.create_task(worker.run()) for worker in workers ], return_when="FIRST_EXCEPTION")
  for task in done_tasks: await task

asyncio.run(main())