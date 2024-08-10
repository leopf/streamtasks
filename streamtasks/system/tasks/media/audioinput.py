from contextlib import asynccontextmanager
from typing import Any
from pydantic import BaseModel
from streamtasks.asgiserver import ASGIRouter, HTTPContext, http_context_handler
from streamtasks.media.audio import get_audio_bytes_per_time_sample
from streamtasks.net.serialization import RawData
from streamtasks.message.types import TimestampChuckMessage
from streamtasks.system.configurators import EditorFields, IOTypes, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client
from streamtasks.system.tasks.media.pa_utils import SAMPLE_FORMAT_2_PA_TYPE
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.utils import get_timestamp_ms
import sounddevice

class AudioInputConfigBase(BaseModel):
  sample_format: IOTypes.SampleFormat = "s16"
  channels: IOTypes.Channels = 1
  rate: IOTypes.SampleRate = 32000
  device_index: int = -1
  buffer_size: int = 4096

class AudioInputConfig(AudioInputConfigBase):
  out_topic: int

class AudioInputTask(SyncTask):
  def __init__(self, client: Client, config: AudioInputConfig):
    super().__init__(client)
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.bytes_per_second = get_audio_bytes_per_time_sample(config.sample_format, config.channels) * config.rate

  @asynccontextmanager
  async def init(self):
    async with self.out_topic, self.out_topic.RegisterContext():
      self.client.start()
      yield

  def run_sync(self):
    device = None if self.config.device_index == -1 else self.config.device_index
    stream = sounddevice.RawInputStream(
      samplerate=self.config.rate,
      blocksize=self.config.buffer_size,
      device=device,
      channels=self.config.channels,
      dtype=SAMPLE_FORMAT_2_PA_TYPE[self.config.sample_format])
    stream.start()
    min_next_timestamp = 0

    while not self.stop_event.is_set():
      data, _ = stream.read(self.config.buffer_size)
      data = bytes(data)
      timestamp = max(get_timestamp_ms(), min_next_timestamp)
      frame_duration = len(data) * 1000 // self.bytes_per_second
      min_next_timestamp = timestamp + frame_duration
      self.send_data(self.out_topic, RawData(TimestampChuckMessage(timestamp=timestamp, data=data).model_dump()))

    stream.close()

class AudioInputTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="audio input",
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "audio", "codec": "raw" }],
    default_config=AudioInputConfigBase().model_dump(),
    config_to_output_map=[ { v: v for v in [ "rate", "channels", "sample_format" ] } ],
    editor_fields=[
      EditorFields.dynamic_select(key="device_index", path="./devices", label="input device"),
      MediaEditorFields.sample_format(allowed_values=set(SAMPLE_FORMAT_2_PA_TYPE.keys())),
      MediaEditorFields.channel_count(),
      MediaEditorFields.sample_rate(),
      MediaEditorFields.audio_buffer_size()
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return AudioInputTask(await self.create_client(topic_space_id), AudioInputConfig.model_validate(config))
  async def register_routes(self, router: ASGIRouter):
    @router.get("/devices")
    @http_context_handler
    async def _(ctx: HTTPContext):
      default_index = sounddevice.default.device[0]
      items = [ { "label": "default", "value": -1 } ]
      items.extend({ "label": d["name"], "value": d["index"] } for d in sounddevice.query_devices() if d["max_input_channels"] > 0 and d["index"] != default_index)
      await ctx.respond_json(items)
