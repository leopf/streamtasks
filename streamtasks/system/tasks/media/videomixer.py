from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from functools import cached_property
import queue
import re
from typing import Any
import numpy as np
from pydantic import BaseModel, ValidationError, field_validator
from streamtasks.client.topic import InTopic, SequentialInTopicSynchronizer
from streamtasks.media.video import TRANSPARENT_PXL_FORMATS
from streamtasks.net.serialization import RawData
from streamtasks.message.types import TimestampChuckMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.system.configurators import EditorFields, IOTypes, multitrackio_configurator, static_configurator
from streamtasks.system.task import SyncTask, TaskHost
from streamtasks.client import Client
from streamtasks.utils import context_task
from streamtasks.media.video_perf import merge_images

class VideoTrackBase(BaseModel):
  label: str = "video track"

class VideoTrack(VideoTrackBase):
  in_topic: int

class VideoMixerConfigBase(BaseModel):
  video_tracks: list[VideoTrack] = []
  width: IOTypes.Width = 1280
  height: IOTypes.Height = 720
  pixel_format: IOTypes.PixelFormat = "bgra"
  rate: IOTypes.FrameRate = 30
  bgcolor_hex: str = "#000000"
  synchronized: bool = True

  @field_validator("pixel_format")
  @classmethod
  def validate_pixel_format(cls, v: str):
    if v not in TRANSPARENT_PXL_FORMATS: raise ValueError("Invalid pixel format!")
    return v

  @field_validator("bgcolor_hex")
  @classmethod
  def validate_bgcolor_hex(cls, v: str):
    if not re.match(r"^#[0-9a-f]{6}$", v, re.IGNORECASE): raise ValueError("Invalid hex string. Must be #RRGGBB (hex).")
    return v

  @cached_property
  def alpha_front(self):
    if self.pixel_format.startswith("a"): return True
    elif self.pixel_format.endswith("a"): return False
    raise ValueError("Alpha channel must be in the front or back!")

  @cached_property
  def bgcolor(self) -> np.ndarray:
    colors = dict(zip("rgba", (int(self.bgcolor_hex[1:3], 16), int(self.bgcolor_hex[3:5], 16), int(self.bgcolor_hex[5:7], 16), 255)))
    return np.array([ colors[c] for c in self.pixel_format.lower() ], dtype=np.uint8)

class VideoMixerConfig(VideoMixerConfigBase):
  out_topic: int

@dataclass
class VideoTrackContext:
  topic: InTopic
  last_message: TimestampChuckMessage | None

@dataclass
class MixingJob:
  timestamp: int
  frames: list[bytes]

class VideoMixerTask(SyncTask):
  def __init__(self, client: Client, config: VideoMixerConfig):
    super().__init__(client)
    if config.synchronized:
      sync = SequentialInTopicSynchronizer()
      in_topics = [ self.client.sync_in_topic(track.in_topic, sync) for track in config.video_tracks ]
    else:
      in_topics = [ self.client.in_topic(track.in_topic) for track in config.video_tracks ]

    self.video_tracks = [ VideoTrackContext(topic=in_topic, last_message=None) for in_topic in in_topics ]
    self.out_topic = self.client.out_topic(config.out_topic)
    self.config = config
    self.frame_count = 0
    self.job_queue: queue.Queue[MixingJob] = queue.Queue()

  @asynccontextmanager
  async def init(self):
    async with AsyncExitStack() as exit_stack:
      await exit_stack.enter_async_context(self.out_topic)
      await exit_stack.enter_async_context(self.out_topic.RegisterContext())

      for video_track in self.video_tracks:
        await exit_stack.enter_async_context(video_track.topic)
        await exit_stack.enter_async_context(video_track.topic.RegisterContext())
        await exit_stack.enter_async_context(context_task(self._run_video_track(video_track)))

      self.client.start()
      yield

  async def _run_video_track(self, track: VideoTrackContext):
    last_frame_count = self.frame_count
    while True:
      try:
        data = await track.topic.recv_data_control()
        if isinstance(data, TopicControlData): track.last_message = None
        else:
          if last_frame_count == self.frame_count: self.submit_job()
          track.last_message = TimestampChuckMessage.model_validate(data.data)
          last_frame_count = self.frame_count
      except ValidationError: pass

  def submit_job(self):
    self.frame_count += 1
    messages = [track.last_message for track in self.video_tracks if track.last_message is not None]
    if len(messages) == 0: return
    self.job_queue.put(MixingJob(
      timestamp=min(m.timestamp for m in messages),
      frames=[ m.data for m in messages ]
    ))

  def run_sync(self):
    timeout = 2 / self.config.rate
    while not self.stop_event.is_set():
      try:
        job = self.job_queue.get(timeout=timeout)
        result = merge_images([ frame for frame in job.frames ], self.config.alpha_front)
        self.send_data(self.out_topic, RawData(TimestampChuckMessage(timestamp=job.timestamp, data=result).model_dump()))
      except queue.Empty: pass

class VideoMixerTaskHost(TaskHost):
  @property
  def metadata(self): return {**static_configurator(
    label="video mixer",
    outputs=[{ "label": "output", "type": "ts", "key": "out_topic", "content": "video", "codec": "raw" }],
    default_config=VideoMixerConfigBase().model_dump(),
    config_to_output_map=[ { v: v for v in [ "rate", "width", "height", "pixel_format" ] } ],
    editor_fields=[
      MediaEditorFields.pixel_format(allowed_values = TRANSPARENT_PXL_FORMATS),
      MediaEditorFields.frame_rate(),
      MediaEditorFields.pixel_size(key="width"),
      MediaEditorFields.pixel_size(key="height"),
      EditorFields.text(key="bgcolor_hex", label="background hex color"),
      EditorFields.boolean(key="synchronized"),
    ]
  ),
  **multitrackio_configurator(is_input=True, track_configs=[{
    "key": "video",
    "ioMap": { "label": "label" },
    "defaultConfig": VideoTrackBase().model_dump(),
    "editorFields": [ EditorFields.text("label") ],
    "defaultIO": { "type": "ts", "content": "video", "codec": "raw" },
    "globalIOMap": { v: v for v in [ "rate", "width", "height", "pixel_format" ] },
  }])}
  async def create_task(self, config: Any, topic_space_id: int | None):
    return VideoMixerTask(await self.create_client(topic_space_id), VideoMixerConfig.model_validate(config))
