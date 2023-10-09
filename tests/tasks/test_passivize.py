import unittest
from .shared import TaskTestBase
from streamtasks.tasks.passivize import PassivizeTask
from streamtasks.system.types import DeploymentTask, TaskInputStream, TaskOutputStream, TaskStreamGroup
import asyncio

@unittest.skip("")
class TestPassivize(TaskTestBase):

  async def asyncSetUp(self):
    await super().asyncSetUp()
    self.stream_in_topic = self.client.create_provide_tracker()
    await self.stream_in_topic.set_topic(100)
    self.stream_active_out_topic = self.client.create_subscription_tracker()
    await self.stream_active_out_topic.set_topic(101)
    self.stream_passive_out_topic = self.client.create_subscription_tracker()
    await self.stream_passive_out_topic.set_topic(102)


  def get_deployment_config(self): return DeploymentTask(
    task_factory_id="test_factory",
    label="test passivize",
    stream_groups=[
      TaskStreamGroup(
        inputs=[ TaskInputStream(topic_id="input", label="input") ],
        outputs=[
          TaskOutputStream(topic_id="active_output", label="active output"),
          TaskOutputStream(topic_id="passive_output", label="passive output")
        ]
      )
    ],
    topic_id_map={
      "input": self.stream_in_topic.topic,
      "active_output": self.stream_active_out_topic.topic,
      "passive_output": self.stream_passive_out_topic.topic
    }
  )

  def start_task(self):
    task = PassivizeTask(self.worker_client, self.get_deployment_config())
    self.tasks.append(asyncio.create_task(task.start()))
    return task

  async def test_sub(self):
    task = self.start_task()
    async with asyncio.timeout(1):
      async with self.client.get_topics_receiver([ self.stream_active_out_topic, self.stream_passive_out_topic ]) as receiver:
        await self.stream_active_out_topic.subscribe()
        await self.stream_in_topic.wait_subscribed()
        await self.stream_passive_out_topic.subscribe()

        await self.stream_active_out_topic.unsubscribe()
        await self.stream_in_topic.wait_subscribed(False)

        await self.stream_active_out_topic.subscribe()
        await self.stream_in_topic.wait_subscribed()

        # await self.client.send_stream_data(self.stream_in_topic.topic, JsonData(NumberMessage(timestamp=1, value=1).model_dump()))
        # await self.stream_passive_out_topic.unsubscribe()
        # await self.client.send_stream_data(self.stream_in_topic.topic, JsonData(NumberMessage(timestamp=1, value=2).model_dump()))
        # await self.stream_passive_out_topic.subscribe()
        # await self.stream_active_out_topic.unsubscribe()
        # await self.client.send_stream_data(self.stream_in_topic.topic, JsonData(NumberMessage(timestamp=1, value=3).model_dump()))

        # messages = [
        #   (1, self.stream_active_out_topic.topic),
        #   (1, self.stream_passive_out_topic.topic),
        #   (2, self.stream_active_out_topic.topic)
        # ]

        # while len(messages) > 0:
        #   topic_id, data, control = await receiver.recv()
        #   if data is None: continue

        #   value = data.data["value"]
        #   timestamp = data.data["timestamp"]
        #   self.assertIn((value, topic_id), messages)
        #   messages.remove((value, topic_id))



