from streamtasks.node import LocalNode
from streamtasks.system.discovery import DiscoveryWorker
from streamtasks.system.workers import TaskManagerWorker
from streamtasks.system.helpers import UvicornASGIServer
from streamtasks.tasks.flowdetector import FlowDetectorTaskFactoryWorker
from streamtasks.tasks.gate import GateTaskFactoryWorker
from streamtasks.tasks.passivize import PassivizeTaskFactoryWorker
import asyncio
import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

async def main():
    node = LocalNode()
    workers = [
        TaskManagerWorker(await node.create_connection(), UvicornASGIServer(8010)),
        DiscoveryWorker(await node.create_connection()),
        GateTaskFactoryWorker(await node.create_connection()),
        PassivizeTaskFactoryWorker(await node.create_connection()),
        FlowDetectorTaskFactoryWorker(await node.create_connection()),
        # CalculatorTaskFactoryWorker(await node.create_connection()),
    ]


    await asyncio.gather(
        node.start(),
        *(worker.start() for worker in workers),
    )

if __name__ == "__main__":
    asyncio.run(main())
