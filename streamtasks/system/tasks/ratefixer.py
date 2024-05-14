from typing import Any, Literal
from pydantic import BaseModel, ValidationError, field_validator
from streamtasks.net.message.types import TopicControlData
from streamtasks.net.message.utils import get_timestamp_from_message
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.utils import get_timestamp_ms
from streamtasks.system.task import Task, TaskHost
from streamtasks.client import Client

class RateFixerConfigBase(BaseModel):
  gain: float = 0.1
  rate: float = 30
  fail_closed: bool = False
  time_reference: Literal["message", "time"] = "time"
  
  @field_validator("gain")
  @classmethod
  def validate_gain(cls, v: float):
    if v < 0 or v > 1: raise ValidationError("gain must be between 0 and 1!")
    return v
  
class RateFixerConfig(RateFixerConfigBase):
  out_topic: int
  in_topic: int

class RateFixerTask(Task):
  def __init__(self, client: Client, config: RateFixerConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config

  async def run(self):
    async with self.out_topic, self.out_topic.RegisterContext(), self.in_topic, self.in_topic.RegisterContext():
      self.client.start()
      last_timestamp: int | None = None
      rate = float(self.config.rate)
      while True:
        data = await self.in_topic.recv_data_control()
        if isinstance(data, TopicControlData):
          await self.out_topic.set_paused(data.paused)
        else:
          try:
            if self.config.time_reference == "message": ref_time = get_timestamp_from_message(data)
            else: ref_time = get_timestamp_ms()
            if last_timestamp is not None:
              current_rate = 1000 / (last_timestamp - ref_time)
              new_rate = (1 - self.config.gain) * rate + self.config.gain * current_rate
            
            rate_diff = new_rate - self.config.rate
            if rate_diff <= 1:
              last_timestamp = ref_time
              rate = new_rate
              repeat_count = int(min(0, -rate_diff))
              await self.out_topic.send(data)
              for _ in range(repeat_count): await self.out_topic.send(data.copy())
              rate += repeat_count
          except:
            if not self.config.fail_closed: await self.out_topic.send(data)

class RateFixerTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="rate fixer",
    inputs=[{ "label": "input", "type": "ts", "key": "in_topic" }],
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic" }],
    config_to_input_map={ "in_topic": { v: v for v in [ "rate" ] } },
    default_config=RateFixerConfigBase().model_dump(),
    io_mirror=[("in_topic", 0)],
    editor_fields=[
      EditorFields.number(key="rate", label="data rate (must match package rate)", is_int=False, unit="hz"),
      EditorFields.slider(key="gain", min_value=0, max_value=1, label="measurement gain", pow=3),
      EditorFields.select(key="time_reference", items=[("time", "time"), ("message", "message")]),
      EditorFields.boolean(key="fail_closed"),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return RateFixerTask(await self.create_client(topic_space_id), RateFixerConfig.model_validate(config))
  