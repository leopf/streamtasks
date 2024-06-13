import asyncio
import importlib.resources
from io import BytesIO
import os
from typing import Any
from pydantic import ValidationError
from streamtasks.asgi import ASGIAppRunner
from streamtasks.asgiserver import ASGIRouter, ASGIServer, HTTPContext, WebsocketContext, http_context_handler, websocket_context_handler
from streamtasks.media.container import OutputContainer
from streamtasks.media.video import VideoCodecInfo
from streamtasks.net.serialization import RawData
from streamtasks.net.utils import endpoint_to_str
from streamtasks.services.protocols import WorkerPorts
from streamtasks.system.configurators import IOTypes, static_configurator
from streamtasks.system.tasks.media.utils import MediaEditorFields
from streamtasks.system.tasks.ui.controlbase import UIControlBaseTaskConfig
from streamtasks.message.types import MediaMessage
from streamtasks.system.task import MetadataFields, Task, TaskHost
from streamtasks.client import Client
from streamtasks.utils import wait_with_dependencies

class VideoViewerConfigBase(UIControlBaseTaskConfig):
  width: IOTypes.Width = 1280
  height: IOTypes.Height = 720
  rate: IOTypes.FrameRate = 30
  pixel_format: IOTypes.PixelFormat = "yuv420p"

class VideoViewerConfig(VideoViewerConfigBase):
  in_topic: int

class VideoViewerTask(Task):
  def __init__(self, client: Client, config: VideoViewerConfig):
    super().__init__(client)
    self.in_topic = self.client.in_topic(config.in_topic)
    self.config = config

  async def setup(self) -> dict[str, Any]:
    self.client.start()
    await self.client.request_address()
    return {
      MetadataFields.ASGISERVER: endpoint_to_str((self.client.address, WorkerPorts.ASGI)),
      "cfg:frontendpath": "index.html",
      **(await super().setup())
    }

  async def run(self):
    app = ASGIServer()
    router = ASGIRouter()
    app.add_handler(router)

    @router.get("/index.html")
    @http_context_handler
    async def _(ctx: HTTPContext):
      with open(importlib.resources.files("streamtasks.system.tasks.ui").joinpath("resources/videoviewer.html")) as fd:
        await ctx.respond_text(fd.read(), mime_type="text/html")

    @router.websocket_route("/video")
    @websocket_context_handler
    async def _(ctx: WebsocketContext):
      in_topic = self.client.in_topic(self.config.in_topic)
      async with in_topic, in_topic.RegisterContext():
        buffer = BytesIO()
        container = await OutputContainer.open(buffer, format="mpegts")
        video_stream = container.add_video_stream(VideoCodecInfo(self.config.width, self.config.height, self.config.rate, self.config.pixel_format, "h264"))
        receive_disconnect_task = asyncio.create_task(ctx.receive_disconnect())

        try:
          await ctx.accept()
          while ctx.connected:
            try:
              data: RawData = await wait_with_dependencies(in_topic.recv_data(), [receive_disconnect_task])
              message = MediaMessage.model_validate(data.data)
              await video_stream.mux(message.packet)
              if buffer.tell() > 0:
                chunk = buffer.getvalue()
                buffer.seek(0, os.SEEK_SET)
                buffer.truncate()
                await ctx.send_message(chunk)
            except ValidationError: pass
        finally:
          await container.close()
          receive_disconnect_task.cancel()
          await ctx.close()

    await ASGIAppRunner(self.client, app).run()


class VideoViewerTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="Video Viewer",
    inputs=[{ "label": "value", "key": "in_topic", "type": "ts", "content": "video", "codec": "h264" }],
    config_to_input_map={ "in_topic": { v: v for v in [ "pixel_format", "rate", "width", "height" ] } },
    default_config=VideoViewerConfigBase().model_dump(),
    editor_fields=[
      MediaEditorFields.pixel_format(),
      MediaEditorFields.pixel_size("width"),
      MediaEditorFields.pixel_size("height"),
      MediaEditorFields.frame_rate(),
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return VideoViewerTask(await self.create_client(topic_space_id), VideoViewerConfig.model_validate(config))
