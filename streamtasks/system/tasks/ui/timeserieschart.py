from contextlib import AsyncExitStack
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ValidationError
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.tasks.ui.controlbase import UIBaseTask, UIControlBaseTaskConfig
from streamtasks.message.types import NumberMessage
from streamtasks.system.task import TaskHost
from streamtasks.client import Client

class TimeSeriesChartConfigBase(UIControlBaseTaskConfig):
  y_label: str = "value"

class TimeSeriesChartConfig(TimeSeriesChartConfigBase):
  in_topic: int

class TimeSeriesValue(BaseModel):
  date: datetime
  value: int | float

class TimeSeriesChartState(BaseModel):
  values: list[TimeSeriesValue]

class TimeSeriesChartTask(UIBaseTask[TimeSeriesChartConfig, TimeSeriesChartState]):
  def __init__(self, client: Client, config: TimeSeriesChartConfig):
    super().__init__(client, config, TimeSeriesChartState(values=[]), "time-series-chart.js")
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config

  async def context(self):
    exit_stack = AsyncExitStack()
    await exit_stack.enter_async_context(self.in_topic)
    await exit_stack.enter_async_context(self.in_topic.RegisterContext())
    return exit_stack

  async def run_other(self):
    while True:
      try:
        data = await self.in_topic.recv_data()
        message = NumberMessage.model_validate(data.data)
        self.value = TimeSeriesChartState(values=self.value.values + [TimeSeriesValue(date=datetime.fromtimestamp(message.timestamp / 1000), value=message.value)])
      except ValidationError: pass

class TimeSeriesChartTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="Time Series Chart",
    inputs=[{ "label": "value", "key": "in_topic", "type": "ts", "content": "number" }],
    default_config=TimeSeriesChartConfigBase().model_dump(),
    editor_fields=[
      EditorFields.text(key="y_label")
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return TimeSeriesChartTask(await self.create_client(topic_space_id), TimeSeriesChartConfig.model_validate(config))
