import argparse
import logging
import os

logging.basicConfig(level=logging.INFO)
os.environ["DATA_DIR"] = ".data"

import asyncio
from streamtasks.connection import NodeServer
from streamtasks.asgi import HTTPServerOverASGI
from streamtasks.client import Client
from streamtasks.client.discovery import wait_for_topic_signal
from streamtasks.net import Switch
from streamtasks.system.connection_manager import ConnectionManager
from streamtasks.services.discovery import DiscoveryWorker
from streamtasks.services.protocols import AddressNames, WorkerTopics
from streamtasks.system.task import TaskManager
from streamtasks.system.task_web import TaskWebBackend
from streamtasks.system.helpers import get_all_task_hosts
from streamtasks.worker import Worker

parser = argparse.ArgumentParser(description="Argument parser for connect and serve URLs")
parser.add_argument("--web-port", help="The port to serve the web dashboard on", default=8080, type=int)
args = parser.parse_args()

async def main():
  switch = Switch()
  client = Client(await switch.add_local_connection())
  client.start()

  discovery = DiscoveryWorker(await switch.add_local_connection())
  discovery_task = asyncio.create_task(discovery.run())
  await wait_for_topic_signal(client, WorkerTopics.DISCOVERY_SIGNAL)

  workers: list[Worker] = [
    TaskManager(await switch.add_local_connection()),
    TaskWebBackend(await switch.add_local_connection()),
    HTTPServerOverASGI(await switch.add_local_connection(), ("localhost", args.web_port), AddressNames.TASK_MANAGER_WEB),
    ConnectionManager(await switch.add_local_connection()),
    NodeServer(await switch.add_local_connection()),
  ]
  for TaskHostCls in get_all_task_hosts(): workers.append(TaskHostCls(await switch.add_local_connection(), register_endpoits=[AddressNames.TASK_MANAGER]))
  done_tasks, _ = await asyncio.wait([discovery_task] + [ asyncio.create_task(worker.run()) for worker in workers ], return_when="FIRST_EXCEPTION")
  for task in done_tasks: await task

asyncio.run(main())
