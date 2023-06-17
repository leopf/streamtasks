from streamtasks.media.types import MediaPacket
from streamtasks.media.video import VideoCodecInfoMinimal, VideoCodecInfo
import av

class InputContainer:
  _container: av.container.InputContainer
  
  def __init__(url: str, topic_encodings: tuple[int, VideoCodecInfo], **kwargs):
    _container = av.open(url, "r", **kwargs)

  async def demux(packets: list[tuple[int, MediaPacket]]):
    loop = asyncio.get_running_loop()
    packet_iter = await loop.run_in_executor(None, self._container.demux)
    while True:
      packet = await loop.run_in_executor(None, packet_iter.__next__)
      
      yield packet 
 

class OutputContainer:
  _container: av.container.OutputContainer
  _stream_index_map: dict[int, int]

  def __init__(self, url_or_path: str, topic_encodings: list[tuple[int, VideoCodecInfoMinimal]], **kwargs):
    self._stream_index_map = {}
    self._container = av.open(url_or_path, "w", **kwargs)
    for topic, codec_info in topic_encodings:
      self._stream_index_map[topic] = len(self._container.streams)
      self._container.add_stream(codec_name=codec_info.codec, rate=codec_info.framerate)

  def __del__(self):
    self.close()

  def close(self):
    self._container.close()

  async def mux(self, packets: list[tuple[int, MediaPacket]]):
    av_packets = []
    for topic, packet in packets:
      av_packet = packet.to_av_packet()
      av_packet.stream = self._container.streams[self._stream_index_map[topic]]
      av_packets.append(av_packet)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, self._mux, av_packets)

  def _mux(self, packets: list[av.Packet]): self._container.mux(packets)