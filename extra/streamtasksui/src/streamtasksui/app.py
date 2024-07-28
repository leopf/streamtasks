import toga.style
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
    self.commands.add(toga.Command(open_docs, "Documentation", group=toga.Group.HELP))

    main_box = toga.Box()
    self.main_window = toga.MainWindow(title=self.formal_name)
    self.main_window.content = main_box
    self.main_window.show()

    self.webview = toga.WebView()
    self.webview.style = toga.style.Pack(flex=1)
    self.webview.set_content(f"http://127.0.0.1:{PORT}/", SPLASHSCREEN)
    main_box.add(self.webview)

    self.add_background_task(self.run_streamtasks)

  async def run_streamtasks(self, *args):
    system = SystemBuilder()
    await system.start_core()
    await system.start_system(PORT)
    while len(system.http_servers) == 0 or system.http_servers[0].server is None or not system.http_servers[0].server.started:
      await asyncio.sleep(0.5)
    await self.webview.load_url(f"http://127.0.0.1:{PORT}/")
    await system.wait_done()

def main(): return streamtasksui()
