import argparse
import ipaddress
import logging
from streamtasks.worker import RemoteClientWorker, RemoteServerWorker
from streamtasks import Node
import asyncio

def validate_args(args):
  if "address" in args: 
    try: ipaddress.ip_address(args["address"])
    except: assert " " not in args["address"]
  if "port" in args: assert args["port"] > 0 and args["port"] < 65535
  if "node_id" in args: assert args["node_id"] > 0
  if "connection_cost" in args: assert args["connection_cost"] > 0

def start_remote_connect(args):
  worker = RemoteClientWorker(args["node_id"], (args["address"], args["port"]), args["connection_cost"])
  asyncio.run(worker.async_start())

def start_remote_listen(args):
  worker = RemoteServerWorker(args["node_id"], (args["address"], args["port"]))
  asyncio.run(worker.async_start())

def start_node(args):
  node = Node(args["node_id"])
  asyncio.run(node.async_start())

def main():
  parser = argparse.ArgumentParser(prog='streamtask workers')
  parser.add_argument('--log-level', '-L', type=str, help='log level', default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
  subparsers = parser.add_subparsers(help='sub-command help', dest="sub")

  parser_node = subparsers.add_parser('node', help='start a node')
  parser_node.add_argument('--node-id', '-I', type=int, help='node id to listen on. Defaults to 1.', default=1)

  parser_remote_connect = subparsers.add_parser('remote-connect', help='start a client worker connecting to a remote address')
  parser_remote_connect.add_argument('--address', '-A', type=str, help='address to listen on', required=True)
  parser_remote_connect.add_argument('--port', '-P', type=int, help='port to listen on', required=True)
  parser_remote_connect.add_argument('--connection-cost', '-C', type=int, help='connection cost (lateny and bandwidth penalty). Defaults to 100.', default=100)
  parser_remote_connect.add_argument('--node-id', '-I', type=int, help='node id to listen on. Defaults to 1.', default=1)

  parser_remote_listen = subparsers.add_parser('remote-listen', help='start a server worker listening on address')
  parser_remote_listen.add_argument('--address', '-A', type=str, help='address to listen on', required=True)
  parser_remote_listen.add_argument('--port', '-P', type=int, help='port to listen on', required=True)
  parser_remote_listen.add_argument('--node-id', '-I', type=int, help='node id to listen on. Defaults to 1.', default=1)

  args = vars(parser.parse_args())
  validate_args(args)
  
  logging.basicConfig(level=args["log_level"])
  logging.debug("starting with args: %s", args)

  if args["sub"] == "node":
    start_node(args)
  elif args["sub"] == "remote-connect":
    start_remote_connect(args)
  elif args["sub"] == "remote-listen":
    start_remote_listen(args)
  else:
    print("Invalid subcommand")
