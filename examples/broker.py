from argparse import ArgumentParser
import asyncio
import logging
from pathlib import Path
from streamtasks.connection import create_server

async def main():
  parser = ArgumentParser("streamtasks broker")
  parser.add_argument("--url", "-U", help="Url to server on.")
  parser.add_argument("--log-level", "-L", help="Log level.", default="DEBUG")
  parser.add_argument("--log-file", help="Log file.", default=None, type=lambda a: None if a is None else Path(a))

  args = parser.parse_args()
  print(args)
  logging.basicConfig(level=logging._nameToLevel[args.log_level.upper()], filename=args.log_file)

  server = create_server(args.url)
  await server.run()

if __name__ == "__main__": asyncio.run(main())
