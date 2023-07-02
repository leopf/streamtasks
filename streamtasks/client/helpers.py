from streamtasks.comm.types import TopicControlData
from typing import TYPE_CHECKING, Iterable
if TYPE_CHECKING:
  from streamtasks.client import Client

import asyncio

class SubscibeContext:
  def __init__(self, client: 'Client', topics: Iterable[int]):
    self._client = client
    self._topics = topics
  async def __aenter__(self): await self._client.subscribe(self._topics)
  async def __aexit__(self, *args): await self._client.unsubscribe(self._topics)
class ProvideContext:
  def __init__(self, client: 'Client', topics: Iterable[int]):
    self._client = client
    self._topics = topics
  async def __aenter__(self): await self._client.provide(self._topics)
  async def __aexit__(self, *args): await self._client.unprovide(self._topics)

class SubscribeTracker:
  def __init__(self, client: 'Client'):
    self._client = client
    self._topic = None
    self._subscribed = False
  async def subscribe(self): 
    if not self._subscribed: 
      self._subscribed = True
      await self._client.subscribe([self._topic])
  async def unsubscribe(self): 
    if self._subscribed: 
      self._subscribed = False
      await self._client.unsubscribe([self._topic])
  @property
  def topic(self): return self._topic
  async def set_topic(self, topic: int, subscribe: bool = True): 
    if topic != self._topic:
      if self._topic is not None: await self._client.unsubscribe([ self._topic ])
      self._subscribed = False
      self._topic = topic
      if self._topic is not None and subscribe: await self._client.subscribe([ self._topic ])
class ProvideTracker:
  def __init__(self, client: 'Client'):
    self._client = client
    self._topic = None
    self._paused = False
  @property
  def is_subscribed(self): return self._client.topic_is_subscribed(self._topic)
  async def wait_subscribed(self, stop_signal: asyncio.Event, subscribed: bool = True): 
    from streamtasks.client.receiver import NoopReceiver
    async with NoopReceiver(self._client):
      while self._client.topic_is_subscribed(self._topic) != subscribed and not stop_signal.is_set(): await asyncio.sleep(0.001)
  async def pause(self):
    if not self._paused:
      self._paused = True
      await self._client.send_stream_control(self._topic, TopicControlData(paused=True))
  async def resume(self):
    if self._paused:
      self._paused = False
      await self._client.send_stream_control(self._topic, TopicControlData(paused=False))
  @property
  def topic(self): return self._topic
  async def set_topic(self, topic: int):
    if topic != self._topic:
      if self._topic is not None: await self._client.unprovide([ self._topic ])
      self._paused = False
      self._topic = topic
      if self._topic is not None: await self._client.provide([ self._topic ])