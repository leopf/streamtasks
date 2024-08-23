from typing import Any
from pydantic import BaseModel
from streamtasks.asgi import ASGIAppRunner, asgi_default_http_error_handler
from streamtasks.asgiserver import ASGIRouter, ASGIServer, HTTPContext, http_context_handler
from streamtasks.net.utils import endpoint_to_str
from streamtasks.services.constants import NetworkPorts
from streamtasks.system.configurators import EditorFields, static_configurator
from streamtasks.system.task import MetadataFields, Task, TaskHost
from streamtasks.client import Client

class WebViewerConfig(BaseModel):
  url: str = ""

def make_html(url: str):
  return f"""
  <!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video Viewer</title>
    <style>
      body, html {{
        margin: 0;
        padding: 0;
        height: 100%;
        overflow: hidden;
      }}
      iframe {{
        width: 100%;
        height: 100%;
        border: none;
      }}
    </style>
  </head>
  <body>
    <iframe src="{url}" allowfullscreen></iframe>
  </body>
  </html>
  """

class WebViewerTask(Task):
  def __init__(self, client: Client, config: WebViewerConfig):
    super().__init__(client)
    self.config = config

  async def setup(self) -> dict[str, Any]:
    self.client.start()
    await self.client.request_address()
    return {
      MetadataFields.ASGISERVER: endpoint_to_str((self.client.address, NetworkPorts.ASGI)),
      "cfg:frontendpath": "index.html",
      **(await super().setup())
    }

  async def run(self):
    app = ASGIServer()
    app.add_handler(asgi_default_http_error_handler)
    router = ASGIRouter()
    app.add_handler(router)

    @router.get("/index.html")
    @http_context_handler
    async def _(ctx: HTTPContext):
       await ctx.respond_text(make_html(self.config.url), mime_type="text/html")

    await ASGIAppRunner(self.client, app).run()


class WebViewerTaskHost(TaskHost):
  @property
  def metadata(self): return static_configurator(
    label="Web Viewer",
    default_config=WebViewerConfig().model_dump(),
    editor_fields=[
      EditorFields.text("url")
    ]
  )
  async def create_task(self, config: Any, topic_space_id: int | None):
    return WebViewerTask(await self.create_client(topic_space_id), WebViewerConfig.model_validate(config))
