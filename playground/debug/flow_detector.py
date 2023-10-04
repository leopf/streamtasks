from streamtasks.helpers import get_timestamp_ms
from streamtasks.message.data import JsonData
from streamtasks.message.structures import NumberMessage
from streamtasks.net import Switch, create_queue_connection
from streamtasks.client import Client
import asyncio

from streamtasks.tasks.flowdetector import FlowDetectorConfig, FlowDetectorFailMode, FlowDetectorTask



async def main():
    switch = Switch()

    conn1 = create_queue_connection(raw=False)
    conn2 = create_queue_connection(raw=True)

    await switch.add_link(conn1[0])
    await switch.add_link(conn2[0])

    client = Client(conn1[1])
    worker_client = Client(conn2[1])
    await asyncio.sleep(0.001)

    in_topic = client.out_topic(100)
    out_topic = client.in_topic(101)
    signal_topic = client.in_topic(102)

    async with in_topic, out_topic, signal_topic:
        client.start()

        task = FlowDetectorTask(worker_client, FlowDetectorConfig(
            fail_mode=FlowDetectorFailMode,
            in_topic=in_topic.topic,
            out_topic=out_topic.topic,
            signal_topic=signal_topic.topic,
        ))
        asyncio.create_task(task.start())
        
        await out_topic.set_registered(True)
        await signal_topic.set_registered(True)
        await in_topic.set_registered(True)

        await in_topic.wait_requested()
        await task.signal_topic.wait_requested()
        await task.out_topic.wait_requested()

        await in_topic.set_paused(True)
        await in_topic.set_paused(False)
        await in_topic.send(JsonData({
          "timestamp": get_timestamp_ms(),
          "value": "HEllo"
        }))
        await in_topic.send(JsonData({
          "timestamp": get_timestamp_ms(),
        }))
        

        while True: 
            data: JsonData = await signal_topic.recv_data()
            message = NumberMessage.model_validate(data.data)
            print("received signal: ", message.value)

if __name__ == "__main__":
    asyncio.run(main())