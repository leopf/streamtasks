from contextlib import asynccontextmanager
import logging
import queue
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.net.serialization import RawData
from streamtasks.message.types import TextMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client
from streamtasks.utils import context_task
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

class LLamaCppChatTask(SyncTask):
  def __init__(self, client: Client, config: LLamaCppChatConfig):
    super().__init__(client)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.message_queue: queue.Queue[TextMessage] = queue.Queue()

  @asynccontextmanager
  async def init(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext(), context_task(self._run_receiver()):
      self.client.start()
      yield

  async def _run_receiver(self):
    while True:
      try:
        data = await self.in_topic.recv_data_control()
        if isinstance(data, TopicControlData): await self.out_topic.set_paused(data.paused)
        else: self.message_queue.put(TextMessage.model_validate(data.data))
      except (ValidationError, ValueError): pass

  def run_sync(self):
    model = Llama(model_path=self.config.model_path, n_gpu_layers=-1 if self.config.use_gpu else 0, verbose=bool(__debug__), n_ctx=self.config.context_length)
    messages: list[ChatCompletionRequestMessage] = []
    if self.config.system_message: messages.append({ "role": "system", "content": self.config.system_message })
    messages_start_index = len(messages)

    while not self.stop_event.is_set():
      try:
        message = self.message_queue.get(timeout=0.5)
        messages.append({ "role": "user", "content": message.value })

        while True:
          end_of_context = False
          result = None
          try:
            result = model.create_chat_completion(messages, max_tokens=self.config.max_tokens or None)
            end_of_context = result["usage"]["total_tokens"] == model.n_ctx()
          except ValueError: end_of_context = True

          if end_of_context and len(messages) > (messages_start_index + 1):
            messages.pop(messages_start_index)
            logging.info("llama.cpp: Removed message from context, to make room for more.")
          elif result is not None:
            amessage = result["choices"][0]["message"]
            messages.append(amessage)
            self.send_data(self.out_topic, RawData(TextMessage(timestamp=message.timestamp, value=amessage["content"]).model_dump()))
            break
          else: raise ValueError("Failed to create response.")
      except queue.Empty: pass

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
