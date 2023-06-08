from typing import Union, Optional, Any
from multiprocessing.connection import Listener, Client, Connection
from abc import ABC, abstractmethod, abstractstaticmethod
from dataclasses import dataclass
from typing_extensions import Self
import asyncio
from streamtasks.communication import *
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
      
class Worker:
  node_id: int
  switch: TopicSwitch
  running: bool

  def __init__(self, node_id: int):
    self.node_id = node_id
    self.switch = TopicSwitch()
    self.running = False

  def signal_stop(self):
    self.running = False

  def create_connection(self) -> TopicConnection:
    connector = create_local_cross_connector()
    self.switch.add_connection(connector[0])
    return connector[1]

  def start(self):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(self.async_start())

  async def async_start(self):
    self.running = True

    while self.running:
      logging.info(f"Connecting to node {self.node_id}")
      try:
        conn = IPCTopicConnection(Client(get_node_socket_path(self.node_id)))
        logging.info(f"Connected to node {self.node_id}")

        self.switch.add_connection(conn)

        while self.running and not conn.connection.closed:
          self.switch.process()
          await asyncio.sleep(0)
      except ConnectionRefusedError:
        logging.info(f"Connection to node {self.node_id} refused")
        await asyncio.sleep(1)

    
    

class Task:
  pass
