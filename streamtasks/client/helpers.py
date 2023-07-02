from streamtasks.comm.types import TopicControlData
from typing import TYPE_CHECKING, Iterable
if TYPE_CHECKING:
    from streamtasks.client import Client

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
  async def set_topic(self, topic: int): 
    if self._topic is not None: await self._client.unsubscribe([ self._topic ])
    self._topic = topic
    if self._topic is not None: await self._client.subscribe([ self._topic ])
class ProvideTracker:
  def __init__(self, client: 'Client'):
    self._client = client
    self._topic = None
    self._paused = False
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
    if self._topic is not None: await self._client.unprovide([ self._topic ])
    self._topic = topic
    if self._topic is not None: await self._client.provide([ self._topic ])