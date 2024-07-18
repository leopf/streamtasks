from typing import Any
from pydantic import BaseModel, field_validator
from streamtasks.net.messages import TopicControlData
from streamtasks.services.protocols import AddressNames
from streamtasks.system.named_topic_manager import NamedTopicRequestModel, NamedTopicResolvedResponseModel
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class NamedInputConfig(BaseModel):
  name: str
  out_topic: int

  @field_validator("name")
  @classmethod
  def validate_name(cls, name: str):
    if name == "named topic": raise ValueError("'named topic' is not allowed as a topic name!")
    return name

class NamedInputTask(Task):
  def __init__(self, client: Client, config: NamedInputConfig):
    super().__init__(client)
    self.config = config
    self.out_topic = client.out_topic(self.config.out_topic)

  async def run(self):
    self.client.start()
    await self.client.request_address()
    response = await self.client.fetch(AddressNames.NAMED_TOPIC_MANAGER, "resolve_named_topic", NamedTopicRequestModel(name=self.config.name))
    in_topic = self.client.in_topic(NamedTopicResolvedResponseModel.model_validate(response).topic)

    async with self.out_topic, self.out_topic.RegisterContext(), in_topic, in_topic.RegisterContext():
      while True:
        data = await in_topic.recv_data_control()
        if isinstance(data, TopicControlData): await self.out_topic.set_paused(data.paused)
        else: await self.out_topic.send(data)

class NamedInputTaskHost(TaskHost):
  @property
  def metadata(self): return {
    "js:configurator": "std:namedinput",
    "cfg:label": "Named Input"
  }
  async def create_task(self, config: Any, topic_space_id: int | None):
    return NamedInputTask(await self.create_client(topic_space_id), NamedInputConfig.model_validate(config))
