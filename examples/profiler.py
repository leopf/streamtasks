import cProfile
import os
import signal
import argparse
import multiprocessing
import time
from uuid import UUID
import requests
from streamtasks.env import WEB_PORT

parser = argparse.ArgumentParser(description="Profiling options")
parser.add_argument("-D", "--deployment-id", type=UUID, required=True)
parser.add_argument("-P", "--web-port", default=WEB_PORT(), type=int)
parser.add_argument("-d", "--duration", default=60, type=int)
parser.add_argument("-o", "--outfile", default=".data/server.prof", type=str)
args, remaining_args = parser.parse_known_args()

def run(): cProfile.run("from streamtasks.bin import main_cli\nmain_cli(remaining_args)", args.outfile)

server = multiprocessing.Process(target=run)
server.start()

while True:
  try:
    requests.post(f"http://localhost:{str(args.web_port)}/api/deployment/{str(args.deployment_id)}/schedule")
    requests.post(f"http://localhost:{str(args.web_port)}/api/deployment/{str(args.deployment_id)}/start")
    break
  except: time.sleep(1)

time.sleep(args.duration)
if server.pid is not None:
  os.kill(server.pid, signal.SIGINT)
server.join()
print("written to: ", args.outfile)
