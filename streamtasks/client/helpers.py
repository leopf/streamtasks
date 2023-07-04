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
    if not self._subscribed and self._topic is not None: 
      self._subscribed = True
      await self._client.subscribe([self._topic])
  async def unsubscribe(self): 
    if self._subscribed and self._topic is not None: 
      self._subscribed = False
      await self._client.unsubscribe([self._topic])
  @property
  def topic(self): return self._topic
  async def set_topic(self, topic: int, subscribe: bool = True): 
    if topic != self._topic:
      await self.unsubscribe()
      self._subscribed = False
      self._topic = topic
      if subscribe: await self.subscribe()
class ProvideTracker:
  def __init__(self, client: 'Client'):
    self._client = client
    self._topic = None
    self._paused = False
  @property
  def is_subscribed(self): return self._client.topic_is_subscribed(self._topic)
  async def wait_subscribed(self, subscribed: bool = True): 
    if self.is_subscribed == subscribed: return # pre check, maybe we can avoid the async context
    from streamtasks.client.receiver import NoopReceiver
    async with NoopReceiver(self._client):
      return await self._client.wait_topic_subscribed(self._topic, subscribed)
  async def pause(self):
    if not self._paused:
      self._paused = True
      if self._topic is not None:
        await self._client.send_stream_control(self._topic, TopicControlData(paused=True))
  async def resume(self):
    if self._paused:
      self._paused = False
      if self._topic is not None:
        await self._client.send_stream_control(self._topic, TopicControlData(paused=False))
  @property
  def topic(self): return self._topic
  async def set_topic(self, topic: int):
    if topic != self._topic:
      if self._topic is not None: await self._client.unprovide([ self._topic ])
      self._paused = False
      self._topic = topic
      if self._topic is not None: await self._client.provide([ self._topic ])