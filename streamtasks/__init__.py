from typing import Union, Optional, Any
from multiprocessing.connection import Listener, Client, Connection
from abc import ABC, abstractmethod, abstractstaticmethod
from dataclasses import dataclass
from typing_extensions import Self
import asyncio
from streamtasks.comm import *
import os 
import logging

class Node:
  id: int
  switch: IPCTopicSwitch
  running: bool

  def __init__(self, id: int):
    self.id = id
    self.switch = IPCTopicSwitch(get_node_socket_path(self.id))
    self.running = False

  def start(self):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(self.async_start())

  def signal_stop(self):
    self.switch.signal_stop()
    self.running = False

  async def async_start(self):
    self.running = True
    await asyncio.gather(
      self.switch.start_listening(),
      self._start_switching()
    )

  async def _start_switching(self):
    while self.running:
      self.switch.process()
      await asyncio.sleep(0)
      
class Task:
  pass
