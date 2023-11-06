from streamtasks.node import LocalNode
from streamtasks.system.discovery import DiscoveryWorker
from streamtasks.system.workers import TaskManagerWorker
from streamtasks.system.helpers import UvicornASGIServer
from streamtasks.tasks.counter import CounterTaskFactoryWorker
from streamtasks.tasks.flowdetector import FlowDetectorTaskFactoryWorker
from streamtasks.tasks.gate import GateTaskFactoryWorker
from streamtasks.tasks.passivize import PassivizeTaskFactoryWorker
import asyncio
import logging
import sys
from tinydb.storages import JSONStorage, MemoryStorage
from pathlib import Path


logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

async def main():
    db_path = str((Path(__file__).parent / "db.json").absolute())
    def FileStorage(): return JSONStorage(db_path, encoding="utf-8")
    
    node = LocalNode()
    workers = [
        TaskManagerWorker(await node.create_link(), UvicornASGIServer(8010)),
        DiscoveryWorker(await node.create_link()),
        GateTaskFactoryWorker(await node.create_link()),
        PassivizeTaskFactoryWorker(await node.create_link()),
        FlowDetectorTaskFactoryWorker(await node.create_link()),
        CounterTaskFactoryWorker(await node.create_link()),
        # CalculatorTaskFactoryWorker(await node.create_link()),
    ]


    await asyncio.gather(
        node.start(),
        *(worker.start() for worker in workers),
    )

if __name__ == "__main__":
    asyncio.run(main())