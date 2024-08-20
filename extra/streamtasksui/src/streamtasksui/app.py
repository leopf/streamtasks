import toga.style
import toga.style.pack
from streamtasks.system.builder import SystemBuilder
import asyncio
import toga
import webbrowser

PORT = 5350

SPLASHSCREEN = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>streamtasks</title>
</head>
<body>
    <div class="container">
        <div class="loader"></div>
    </div>
    <style>
        body {
            margin: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: black;
        }
        .container {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100vw;
            height: 100vh;
        }
        .loader {
            border: 1rem solid #333;
            border-radius: 50%;
            border-top: 1rem solid #000;
            width: 8rem;
            height: 8rem;
            -webkit-animation: spin 2s linear infinite; /* Safari */
            animation: spin 2s linear infinite;
        }

        /* Safari */
        @-webkit-keyframes spin {
            0% { -webkit-transform: rotate(0deg); }
            100% { -webkit-transform: rotate(360deg); }
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</body>
</html>
"""
def open_docs(*args): webbrowser.open("https://leopf.github.io/streamtasks/")

class streamtasksui(toga.App):
  def startup(self):
    self.connect_url = None
    self.system: SystemBuilder | None = None

    self.commands.add(toga.Command(open_docs, "Documentation", group=toga.Group.HELP))
    self.stop_system_command = toga.Command(self._stop_system, "stop system", group=toga.Group.APP, enabled=False)
    self.commands.add(self.stop_system_command)

    self.main_box = toga.Box()
    self.webview = toga.WebView()
    self.webview.style = toga.style.Pack(flex=1)
    self.main_box.add(self.webview)

    self.config_box = toga.Box()
    self.config_box.style.direction = toga.style.pack.COLUMN
    self.config_box.style.padding = 10

    start_main_button = toga.Button("Start new instance")
    start_main_button.on_press = self._start_new_instance

    connect_box = toga.Box()
    connect_box.style.padding_bottom = 20
    connect_box.style.alignment = "bottom"

    connect_url_box = toga.Box()
    connect_url_box.style.flex = 1
    connect_url_box.style.direction = toga.style.pack.COLUMN
    connect_url_box.style.padding_right = 10

    connect_url_text_field_label = toga.Label("connect to URL:")
    self.connect_url_text_field = toga.TextInput()
    connect_url_box.add(connect_url_text_field_label, self.connect_url_text_field)

    self.connect_to_instance_button = toga.Button("Connect to instance")
    self.connect_to_instance_button.on_press = self._connect_to_instance

    connect_box.add(connect_url_box, self.connect_to_instance_button)
    flex_spacer = toga.Box()
    flex_spacer.style.flex = 1

    self.error_text = toga.Label("")
    self.error_text.style.visibility = "hidden"
    self.error_text.style.color = "red"
    self.error_text.style.text_align = "center"
    self.error_text.style.font_size = 12

    self.config_box.add(connect_box, start_main_button, flex_spacer, self.error_text)

    self.main_window = toga.MainWindow(title=self.formal_name)
    self.main_window.content = self.config_box
    self.main_window.show()

  async def run_streamtasks_sub(self, *args):
    system = SystemBuilder()
    await system.start_connector(self.connect_url)
    await self.run_streamtasks(system)

  async def run_streamtasks_main(self, *args):
    system = SystemBuilder()
    await system.start_core()
    await self.run_streamtasks(system)

  async def run_streamtasks(self, system: SystemBuilder):
    error_text = None

    self.main_window.content = self.main_box
    self.stop_system_command.enabled = True
    self.webview.set_content(f"http://127.0.0.1:{PORT}/", SPLASHSCREEN)

    try:
      await system.start_system(PORT)
      while len(system.http_servers) == 0 or system.http_servers[0].server is None or not system.http_servers[0].server.started:
        await asyncio.sleep(0.5)
      await self.webview.load_url(f"http://127.0.0.1:{PORT}/")
      await system.wait_done()
    except BaseException as e:
      if not isinstance(e, asyncio.CancelledError):
        error_text = str(e)
    finally:
      self.stop_system_command.enabled = False
      if error_text is not None:
        self.error_text.style.visibility = "visible"
        self.error_text.text = error_text
      else:
        self.error_text.style.visibility = "hidden"
      self.main_window.content = self.config_box

  def _connect_to_instance(self, *args):
    self.connect_url = self.connect_url_text_field.value
    self.add_background_task(self.run_streamtasks_sub)

  def _start_new_instance(self, *args):
    self.add_background_task(self.run_streamtasks_main)

  def _stop_system(self, *args):
    if self.system is not None: self.system.cancel_all()

def main(): return streamtasksui()
