from streamtasks.net.types import TopicControlData
from typing import TYPE_CHECKING, Iterable
if TYPE_CHECKING:
  from streamtasks.client import Client

class SubscribeTracker:
  def __init__(self, client: 'Client'):
    self._client = client
    self._topic = None
    self._subscribed = False
  async def set_subscribed(self, subscribed: bool):
    if subscribed: await self.subscribe()
    else: await self.unsubscribe()
  async def subscribe(self): 
    if not self._subscribed and self._topic is not None: 
      self._subscribed = True
      await self._client.register_in_topics([self._topic])
  async def unsubscribe(self): 
    if self._subscribed and self._topic is not None: 
      self._subscribed = False
      await self._client.unregister_in_topics([self._topic])
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
  def paused(self): return self._paused
  @property
  def is_subscribed(self): return self._client.topic_is_subscribed(self._topic)
  async def wait_subscribed_change(self): return await self.wait_subscribed(not self.is_subscribed)
  async def wait_subscribed(self, subscribed: bool = True): 
    if self.is_subscribed == subscribed: return # pre check, maybe we can avoid the async context
    from streamtasks.client.receiver import NoopReceiver
    async with NoopReceiver(self._client):
      return await self._client.wait_topic_subscribed(self._topic, subscribed)
  async def set_paused(self, paused: bool): 
    if self._paused != paused:
      self._paused = paused
      if self._topic is not None: await self._client.send_stream_control(self._topic, TopicControlData(paused=paused))
  async def pause(self): await self.set_paused(True)
  async def resume(self): await self.set_paused(False)
  @property
  def topic(self): return self._topic
  async def set_topic(self, topic: int):
    if topic != self._topic:
      if self._topic is not None: await self._client.unregister_out_topics([ self._topic ])
      self._paused = False
      self._topic = topic
      if self._topic is not None: await self._client.register_out_topics([ self._topic ])