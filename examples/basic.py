import os
import logging

from streamtasks.system.tasks.videodecoder import VideoDecoderTaskHost
from streamtasks.system.tasks.videoencoder import VideoEncoderTaskHost
from streamtasks.system.tasks.videoinput import VideoInputTaskHost
logging.basicConfig(level=logging.INFO)
os.environ["DATA_DIR"] = ".data"

import asyncio
from streamtasks.asgi import HTTPServerOverASGI
from streamtasks.client import Client
from streamtasks.client.discovery import wait_for_topic_signal
from streamtasks.net import Switch
from streamtasks.services.discovery import DiscoveryWorker
from streamtasks.services.protocols import AddressNames, WorkerTopics
from streamtasks.system.task import TaskManager
from streamtasks.system.task_web import TaskWebBackend
from streamtasks.system.tasks.pulsegenerator import IdPulseGeneratorTaskHost, TimePulseGeneratorTaskHost
from streamtasks.system.tasks.timestampupdater import TimestampUpdaterTaskHost
from streamtasks.worker import Worker

async def main():
  switch = Switch()
  client = Client(await switch.add_local_connection())
  client.start()
  
  discovery = DiscoveryWorker(await switch.add_local_connection())
  discovery_task = asyncio.create_task(discovery.run())
  await wait_for_topic_signal(client, WorkerTopics.DISCOVERY_SIGNAL)
  
  workers: list[Worker] = [
    TaskManager(await switch.add_local_connection()),
    TaskWebBackend(await switch.add_local_connection(), public_path="web/dist"),
    HTTPServerOverASGI(await switch.add_local_connection(), ("127.0.0.1", 8080), AddressNames.TASK_MANAGER_WEB),
    TimePulseGeneratorTaskHost(await switch.add_local_connection(), register_endpoits=[AddressNames.TASK_MANAGER]),
    IdPulseGeneratorTaskHost(await switch.add_local_connection(), register_endpoits=[AddressNames.TASK_MANAGER]),
    TimestampUpdaterTaskHost(await switch.add_local_connection(), register_endpoits=[AddressNames.TASK_MANAGER]),
    VideoInputTaskHost(await switch.add_local_connection(), register_endpoits=[AddressNames.TASK_MANAGER]),
    VideoEncoderTaskHost(await switch.add_local_connection(), register_endpoits=[AddressNames.TASK_MANAGER]),
    VideoDecoderTaskHost(await switch.add_local_connection(), register_endpoits=[AddressNames.TASK_MANAGER]),
  ]
  
  tasks = await asyncio.wait([discovery_task] + [ asyncio.create_task(worker.run()) for worker in workers ], return_when="FIRST_COMPLETED")
  print(tasks)

asyncio.run(main())