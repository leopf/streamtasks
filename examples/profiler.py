import cProfile
import os
import signal
import argparse
import multiprocessing
import time
from uuid import UUID
import requests

parser = argparse.ArgumentParser(description="Profiling options")
parser.add_argument("-D", "--deployment-id", type=UUID)
parser.add_argument("-P", "--web-port", default=8080, type=int)
parser.add_argument("-d", "--duration", default=60, type=int)
parser.add_argument("-o", "--outfile", default=".data/server.prof", type=str)
args, remaining_args = parser.parse_known_args()

def run(): cProfile.run("main_cli(remaining_args)", args.outfile)

server = multiprocessing.Process(target=run)
server.start()

while True:
  try:
    requests.post(f"http://localhost:{str(args.web_port)}/api/deployment/{str(args.deployment_id)}/schedule")
    requests.post(f"http://localhost:{str(args.web_port)}/api/deployment/{str(args.deployment_id)}/start")
    break
  except: time.sleep(1)

signal.signal(signal.SIGALRM, lambda *args: os.kill(server.pid, signal.SIGINT))
signal.alarm(args.duration)
server.join()
print("written to: ", args.outfile)
