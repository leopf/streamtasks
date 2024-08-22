import asyncio
from typing import Iterable, TypeVar
from pydantic import TypeAdapter
from streamtasks.client import Client
from streamtasks.client.fetch import FetchRequest, FetchServer
from streamtasks.client.receiver import Receiver
from streamtasks.net import EndpointOrAddress, endpoint_or_address_to_endpoint
from streamtasks.net.serialization import RawData
from streamtasks.net.messages import Message, TopicDataMessage
from streamtasks.services.constants import NetworkPorts

class BroadcastingServer:
  def __init__(self, client: 'Client', port: int = NetworkPorts.BROADCAST) -> None:
    self.port = port
    self.client = client
    self.namespaces: dict[str, int] = {}

  async def broadcast(self, ns: str, data: RawData):
    if (topic_id := self.namespaces.get(ns, None)) != None:
      await self.client.send_stream_data(topic_id, data)

  async def run(self):
    NamespaceList = TypeAdapter(list[str])
    try:
      server = FetchServer(self.client, port=self.port)

      @server.route("gettopics")
      async def _(req: FetchRequest):
        req_namespaces = NamespaceList.validate_python(req.body)
        missing_namespaces = [ ns for ns in req_namespaces if ns not in self.namespaces ]
        new_topic_ids = await self.client.request_topic_ids(len(missing_namespaces), apply=True)
        for ns, topic_id in zip(missing_namespaces, new_topic_ids): self.namespaces[ns] = topic_id
        await req.respond({ ns: topic_id for ns, topic_id in self.namespaces.items() if ns in req_namespaces })

      await server.run()
    finally:
      await self.client.unregister_out_topics(self.namespaces.values(), force=True)
      self.namespaces = {}

T = TypeVar("T")
class BroadcastReceiver(Receiver[T]):
  def __init__(self, client: 'Client', namespaces: Iterable[str], endpoint: EndpointOrAddress):
    super().__init__(client)
    self._recv_queue: asyncio.Queue[T]
    self._namespaces = set(namespaces)
    self._endpoint = endpoint_or_address_to_endpoint(endpoint, NetworkPorts.BROADCAST)
    self._topics_ns_map: dict[int, str] = {}

  async def _on_start_recv(self):
    ns_topic_map: dict[int, str] = await self._client.fetch(self._endpoint, "gettopics", list(self._namespaces))
    self._topics_ns_map: dict[int, str] = { v:k for k, v in ns_topic_map.items() }
    await self._client.register_in_topics(self._topics_ns_map.keys())
  async def _on_stop_recv(self):
    await self._client.unregister_in_topics(self._topics_ns_map.keys())

  def on_message(self, message: Message):
    if isinstance(message, TopicDataMessage) and message.topic in self._topics_ns_map:
      self._recv_queue.put_nowait(self.transform_data(self._topics_ns_map[message.topic], message.data))
  def transform_data(self, namespace: str, data: RawData) -> T: return (namespace, data)
