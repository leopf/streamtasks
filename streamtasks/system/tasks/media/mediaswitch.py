from typing import Any
from pydantic import ValidationError
from streamtasks.client.topic import InTopic
from streamtasks.message.types import MediaMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.task import TaskHost
from streamtasks.client import Client
from streamtasks.system.tasks.switch import SwitchConfig, SwitchTask

class MediaSwitchTask(SwitchTask):
  def __init__(self, client: Client, config: SwitchConfig):
    super().__init__(client, config)
    self._active_index = -1

  async def _run_input_receiver(self, topic: InTopic, idx: int):
    while True:
      data = await topic.recv_data_control()
      if self._get_selected_index() == idx:
        await self.out_topic.set_paused(topic.is_paused)
        if not isinstance(data, TopicControlData):
          if idx != self._active_index:
            try:
              message = MediaMessage.model_validate(data.data)
              if message.packet.is_keyframe: self._active_index = idx
            except ValidationError: pass
          if idx == self._active_index:
            await self.out_topic.send(data)

class MediaSwitchTaskHost(TaskHost):
  @property
  def metadata(self): return {
    "js:configurator": "std:switch",
    "cfg:label": "Media Switch"
  }
  async def create_task(self, config: Any, topic_space_id: int | None):
    return MediaSwitchTask(await self.create_client(topic_space_id), SwitchConfig.model_validate(config))
