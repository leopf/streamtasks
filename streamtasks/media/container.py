from streamtasks.media.types import MediaPacket
from streamtasks.media.codec import CodecInfo, Frame, Transcoder, EmptyTranscoder
from typing import AsyncIterable
import av

class InputContainer:
  _container: av.container.InputContainer
  _transcoder_map: dict[int, Transcoder]
  _stream_index_map: dict[int, int]
  
  def __init__(url: str, topic_encodings: list[tuple[int, VideoCodecInfo]], **kwargs):
    self._container = av.open(url, "r", **kwargs)
    stream_codec_infos = [ (stream.index, CodecInfo.from_codec_context(stream.codec_context)) for stream in self._container.streams ]
    # find compatible streams
    self._stream_index_map = {}
    self._transcoder_map = {}
    # assing streams to topics and create transcoders

    # for stream_index in range(len(stream_codec_infos)):
    #   for topic, codec_info in topic_encodings:
    #     if codec_info.compatible_with(stream_codec_infos[stream_index][1]):
    #       self._stream_index_map[topic] = stream_index
    #       self._transcoder_map[topic] = EmptyTranscoder()
    #       break
    
    # for topic, codec_info in topic_encodings:
    #   if topic in self._stream_index_map: continue

    #   [ for stream_index, stream_codec_info in stream_codec_infos if codec_info.compatible_with(stream_codec_info) ]


  async def demux(packets: list[tuple[int, MediaPacket]]) -> AsyncIterable[tuple[int, MediaPacket]]:
    loop = asyncio.get_running_loop()
    packet_iter = await loop.run_in_executor(None, self._container.demux)
    while True:
      packet = await loop.run_in_executor(None, packet_iter.__next__)
      if packet is None: break

      topic = self._stream_index_map[packet.stream_index]
      transcoder = self._transcoder_map[packet.stream_index]

      for packet in await transcoder.transcode(packet):
        yield (topic, packet) 

  def close(self):
    self._container.close()

class OutputContainer:
  _container: av.container.OutputContainer
  _stream_index_map: dict[int, int]

  def __init__(self, url_or_path: str, topic_encodings: list[tuple[int, CodecInfo]], **kwargs):
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