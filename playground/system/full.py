from streamtasks.node import LocalNode
from streamtasks.system.discovery import DiscoveryWorker
from streamtasks.system.workers import TaskManagerWorker
from streamtasks.system.helpers import UvicornASGIServer
from streamtasks.tasks.calculator import CalculatorTaskFactoryWorker
from streamtasks.tasks.flowdetector import FlowDetectorTaskFactoryWorker
from streamtasks.tasks.gate import GateTaskFactoryWorker
from streamtasks.tasks.passivize import PassivizeTaskFactoryWorker
import asyncio


async def run():
    node = LocalNode()
    task_manager = TaskManagerWorker(await node.create_connection(), UvicornASGIServer("8010"))
    discovery = DiscoveryWorker(await node.create_connection())
    calculator = CalculatorTaskFactoryWorker(await node.create_connection())
    flow_detector = FlowDetectorTaskFactoryWorker(await node.create_connection())
    gate = GateTaskFactoryWorker(await node.create_connection())
    passivize = PassivizeTaskFactoryWorker(await node.create_connection())

    await asyncio.gather(
        node.start(),
        discovery.start(),
        task_manager.start(),
        calculator.start(),
        flow_detector.start(),
        gate.start(),
        passivize.start()
    )

async def main():
    task = asyncio.create_task(run())
    try:
        await task
    except KeyboardInterrupt:
        print("interrupted")
        task.cancel()
        await task


if __name__ == "__main__":
    asyncio.run(main())


