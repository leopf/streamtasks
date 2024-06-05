from functools import reduce
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.net.serialization import RawData
from streamtasks.message.types import NumberMessage, TextMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
import re

class StringMatcherConfigBase(BaseModel):
  pattern: str = ""
  flags: str = "i"
  is_regex: bool = False

class StringMatcherConfig(StringMatcherConfigBase):
  out_topic: int
  in_topic: int

class StringMatcherTask(Task):
  def __init__(self, client: Client, config: StringMatcherConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)

    pattern = config.pattern
    if not config.is_regex: pattern = "^.*(" + re.escape(pattern) + ").*$"

    flags = reduce(lambda pv, cv: pv | cv, [ re.RegexFlag._member_map_[f].value for f in config.flags.upper() if f in re.RegexFlag._member_map_ ], 0)
    self.regex = re.compile(pattern, flags)

  async def run(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      while True:
        try:
          data = await self.in_topic.recv_data_control()
          if isinstance(data, TopicControlData):
            await self.out_topic.set_paused(data.paused)
          else:
            message = TextMessage.model_validate(data.data)
            await self.out_topic.send(RawData(NumberMessage(timestamp=message.timestamp, value=0 if self.regex.match(message.value) is None else 1).model_dump()))
        except ValidationError: pass

class StringMatcherTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="string matcher",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "content": "text" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "number" }],
    default_config=StringMatcherConfigBase().model_dump(),
    editor_fields=[
      EditorFields.text(key="pattern", label="pattern to match"),
      EditorFields.text(key="flags", label="regular expression flags"),
      EditorFields.boolean(key="is_regex", label="is regular expression"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return StringMatcherTask(await self.create_client(topic_space_id), StringMatcherConfig.model_validate(config))
