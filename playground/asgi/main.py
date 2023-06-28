from fastapi import FastAPI
from streamtasks.worker import Worker
from streamtasks.node import LocalNode
from streamtasks.client import Client
from streamtasks.client.asgi import *
import uvicorn
import cProfile
import signal
import os
import asyncio

node = LocalNode()
processing_tasks: list[asyncio.Task] = []
stop_signal = asyncio.Event()

async def demo_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200})
    await send({"type": "http.response.body", "body": b"Hello world!"})

async def setup_worker(worker: Worker):
    await worker.set_node_connection(await node.create_connection(raw=True))
    processing_tasks.append(asyncio.create_task(worker.async_start(stop_signal)))

async def start_node():
    processing_tasks.append(asyncio.create_task(node.async_start(stop_signal)))

async def start_secondary_server():
    worker = Worker(2)
    await setup_worker(worker)

    client = Client(await worker.create_connection())
    await client.change_addresses([1337])

    app = FastAPI()
    @app.get("/")
    def read_root():
        return "hi from secondary server"

    runner = ASGIAppRunner(client, demo_app, "demo_app", 1337)
    processing_tasks.append(asyncio.create_task(runner.async_start(stop_signal)))

async def start_main_server():
    worker = Worker(1)
    await setup_worker(worker)

    client = Client(await worker.create_connection())
    await client.change_addresses([1338])

    app = FastAPI()

    @app.get("/")
    def read_root():
        return {"Hello": "World"}

    demo_proxy_app = ASGIProxyApp(client, 1337, "demo_app")
    async def wrap_demo_app(scope, receive, send):
        try:
            await demo_proxy_app(scope, receive, send)
            print("demo app finished")
        except Exception as e:
            print(e)
            raise e
    app.mount("/demo", wrap_demo_app)

    config = uvicorn.Config(app, port=8000)
    server = uvicorn.Server(config)
    await server.serve()
    stop_signal.set()

    for task in processing_tasks: await task

async def main():
    await start_node()
    await start_secondary_server()
    await start_main_server()
    await stop_signal.wait()

if __name__ == "__main__":
    # asyncio.run(main())
    # exit(0)

    profiler = cProfile.Profile()
    profiler.enable()

    def timeout_handler(signum, frame):
        stop_signal.set()
        raise TimeoutError("Program execution timed out")
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(20)

    try:
        asyncio.run(main())
    except:
        pass

    profiler.disable()
    # stats next to this file
    profiler.dump_stats(os.path.join(os.path.dirname(__file__), "profile.prof"))