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
  _connection: TopicConnection
  _provides_topics: set[int]
  _subscribed_topics: set[int]

  def __init__(self, connection: TopicConnection):
    self._connection = connection
    self._provides_topics = set()
    self._subscribed_topics = set()

  def subscribe(self, topics: Iterable[int]):
    new_subscribed = set(topics)
    remove_subscribed = self._subscribed_topics - new_subscribed
    add_subscribed = new_subscribed - self._subscribed_topics
    for topic in remove_subscribed: self._connection.send(UnsubscribeMessage(topic))
    for topic in add_subscribed: self._connection.send(SubscribeMessage(topic))
    self._subscribed_topics = new_subscribed

  def provide(self, topics: Iterable[int]):
    new_provides = set(topics)
    remove_provided = self._provides_topics - new_provides
    add_provided = new_provides - self._provides_topics
    self._connection.send(ProvidesMessage(set([ PricedTopic(topic, 0) for topic in add_provided ]), remove_provided))
    self._provides_topics = new_provides

  def pause(self):
    for topic in self._provides_topics: self._connection.send(StreamControlMessage(topic, True))
    for topic in self._subscribed_topics: self._connection.send(UnsubscribeMessage(topic))

  def resume(self):
    for topic in self._provides_topics: self._connection.send(StreamControlMessage(topic, False))
    for topic in self._subscribed_topics: self._connection.send(SubscribeMessage(topic))
      
  
  
