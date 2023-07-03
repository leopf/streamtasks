import asyncio

queue = asyncio.Queue()
closed = asyncio.Event()
processed = asyncio.Event()

async def recv():
    while True:
        done, pending = await asyncio.wait(
            [asyncio.create_task(queue.get()), asyncio.create_task(closed.wait())],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        print(next(iter(done)).result())

        for task in pending:
            task.cancel()
        
        processed.set()

async def main():
    asyncio.create_task(recv())
    
    closed.set()
    
    await processed.wait()
    processed.clear()

    closed.set()

    await processed.wait()
    processed.clear()

    await queue.put(1)

    await processed.wait()
    processed.clear()

    await queue.put(2)

    await processed.wait()
    processed.clear()

    await queue.put(3)

    await processed.wait()
    processed.clear()

    closed.set()

    await processed.wait()
    processed.clear()



if __name__ == "__main__":
    asyncio.run(main())