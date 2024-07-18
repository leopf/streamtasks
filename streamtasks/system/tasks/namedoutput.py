from typing import Any
from pydantic import BaseModel, field_validator
from streamtasks.net.messages import TopicControlData
from streamtasks.services.protocols import AddressNames
from streamtasks.system.named_topic_manager import NamedTopicModel, NamedTopicRequestModel, NamedTopicResolvedResponseModel
from streamtasks.system.task import MetadataDict, Task, TaskHost
from streamtasks.client import Client

class NamedOutputConfig(BaseModel):
  name: str
  metadata: MetadataDict
  in_topic: int

  @field_validator("name")
  @classmethod
  def validate_name(cls, name: str):
    if name == "named topic": raise ValueError("'named topic' is not allowed as a topic name!")
    return name

class NamedOutputTask(Task):
  def __init__(self, client: Client, config: NamedOutputConfig):
    super().__init__(client)
    self.config = config
    self.in_topic = client.in_topic(self.config.in_topic)

  async def run(self):
    self.client.start()
    await self.client.request_address()
    await self.client.fetch(AddressNames.NAMED_TOPIC_MANAGER, "put_named_topic", NamedTopicModel(name=self.config.name, metadata=self.config.metadata).model_dump())
    response = await self.client.fetch(AddressNames.NAMED_TOPIC_MANAGER, "resolve_named_topic", NamedTopicRequestModel(name=self.config.name).model_dump())
    out_topic = self.client.out_topic(NamedTopicResolvedResponseModel.model_validate(response).topic)

    async with self.in_topic, self.in_topic.RegisterContext(), out_topic, out_topic.RegisterContext():
      while True:
        data = await self.in_topic.recv_data_control()
        if isinstance(data, TopicControlData): await out_topic.set_paused(data.paused)
        else: await out_topic.send(data)

class NamedOutputTaskHost(TaskHost):
  @property
  def metadata(self): return {
    "js:configurator": "std:namedoutput",
    "cfg:label": "Named Output"
  }
  async def create_task(self, config: Any, topic_space_id: int | None):
    return NamedOutputTask(await self.create_client(topic_space_id), NamedOutputConfig.model_validate(config))
