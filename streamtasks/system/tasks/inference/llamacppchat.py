import asyncio
import functools
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.env import DEBUG
from streamtasks.net.message.data import MessagePackData
from streamtasks.net.message.structures import TextMessage
from streamtasks.net.message.types import TopicControlData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client
from llama_cpp import ChatCompletionRequestMessage, Llama

class LLamaCppChatConfigBase(BaseModel):
  model_path: str = ""
  use_gpu: bool = False
  context_length: int = 512
  max_tokens: int = 0
  system_message: str = ""

class LLamaCppChatConfig(LLamaCppChatConfigBase):
  out_topic: int
  in_topic: int

class LLamaCppChatTask(Task):
  def __init__(self, client: Client, config: LLamaCppChatConfig):
    super().__init__(client)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config

  async def run(self):
    loop = asyncio.get_running_loop()
    model = await loop.run_in_executor(None, self.load_model)
    messages: list[ChatCompletionRequestMessage] = []
    if self.config.system_message: messages.append({ "role": "system", "content": self.config.system_message })

    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      while True:
        try:
          data = await self.in_topic.recv_data_control()
          if isinstance(data, TopicControlData): await self.out_topic.set_paused(data.paused)
          else:
            message = TextMessage.model_validate(data.data)
            messages.append({ "role": "user", "content": message.value })
            result = await loop.run_in_executor(None, functools.partial(model.create_chat_completion, messages, max_tokens=self.config.max_tokens or None))
            if len(result["choices"]) > 0:
              amessage = result["choices"][0]["message"]
              messages.append(amessage)
              print(result)
              await self.out_topic.send(MessagePackData(TextMessage(timestamp=message.timestamp, value=amessage["content"]).model_dump()))
        except (ValidationError, ValueError): pass

  def load_model(self): return Llama(model_path=self.config.model_path, n_gpu_layers=-1 if self.config.use_gpu else 0, verbose=bool(DEBUG()), n_ctx=self.config.context_length)

class LLamaCppChatTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="llama.cpp Chat",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic", "content": "text" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "text" }],
    default_config=LLamaCppChatConfigBase().model_dump(),
    editor_fields=[
      EditorFields.text(key="model_path"),
      EditorFields.multiline_text(key="system_message"),
      EditorFields.integer(key="context_length", min_value=0),
      EditorFields.integer(key="max_tokens", min_value=0),
      EditorFields.boolean(key="use_gpu"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return LLamaCppChatTask(await self.create_client(topic_space_id), LLamaCppChatConfig.model_validate(config))
