from argparse import ArgumentParser
import asyncio
import logging
from pathlib import Path
from streamtasks.system.builder import SystemBuilder

async def main(args: list[str] | None = None):
  parser = ArgumentParser("Streamtasks")
  parser.add_argument("--core", "-C", action="store_true", help="Flag indicating whether to run the core components (only allowed to be run once per system, by default).")
  parser.add_argument("--connect", action="append", help="Urls to connect to.")
  parser.add_argument("--serve", action="append", help="Urls to serve on.")
  parser.add_argument("--web-port", "-P", type=int, default=9006, help="Port to serve the web dashboard on.")
  parser.add_argument("--web-view", "-V", action="store_true", help="Flag indicating whether to show the web view.")

  parser.add_argument("--log-level", "-L", help="Log level.", default="DEBUG")
  parser.add_argument("--log-file", help="Log file.", default=None, type=lambda a: None if a is None else Path(a))

  args = parser.parse_args(args)

  logging.basicConfig(level=logging._nameToLevel[args.log_level.upper()], filename=args.log_file)

  builder = SystemBuilder()
  if args.core: await builder.start_core()
  if args.connect:
    for url in args.connect: await builder.start_connector(url)
  if args.serve:
    for url in args.serve: await builder.start_server(url)

  await builder.start_system(args.web_port, args.web_view)
  await builder.wait_done()

def main_cli(args: list[str] | None = None): asyncio.run(main(args))

if __name__ == "__main__": main_cli()
