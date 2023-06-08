from typing import Union, Optional, Any
from multiprocessing.connection import Listener, Client, Connection
from abc import ABC, abstractmethod, abstractstaticmethod
from dataclasses import dataclass
from typing_extensions import Self
import asyncio
from streamtasks.comm import *
import os 
import logging


def get_node_socket_path(id: int) -> str:
  if os.name == 'nt':
      return f'\\\\.\\pipe\\streamtasks-{id}'
  else:
      return f'/run/streamtasks-{id}.sock'


class Node:
  id: int
  switch: TopicSwitch
  running: bool

  def __init__(self, id: int):
    self.id = id
    self.switch = TopicSwitch()
    self.running = False

  def start(self):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(self.async_start())

  def signal_stop(self):
    self.running = False

  async def async_start(self):
    self.running = True
    await asyncio.gather(
      self._start_listening(),
      self._start_switching()
    )

  async def _start_switching(self):
    while self.running:
      self.switch.process()
      await asyncio.sleep(0)

  async def _start_listening(self):
    loop = asyncio.get_event_loop()
    listerner = Listener(get_node_socket_path(self.id))
    while self.running:
      conn = await loop.run_in_executor(None, listerner.accept)
      self.switch.add_connection(IPCTopicConnection(conn))
      

    
class Task:
  pass
