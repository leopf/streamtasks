from streamtasks.media.types import MediaPacket
from streamtasks.media.codec import CodecInfo, Frame, Transcoder, EmptyTranscoder, AVTranscoder, Decoder, CodecOptions
from streamtasks.media.config import *
from typing import AsyncIterable
import av
import asyncio
import time

class InputContainer:
  _container: av.container.InputContainer
  _transcoder_map: dict[int, Transcoder]
  _stream_index_map: dict[int, int]
  _t0: int
  
  def __init__(self, url: str, topic_encodings: list[tuple[int, CodecInfo]], codec_options: CodecOptions = {}, **kwargs):
    self._container = av.open(url, "r", **kwargs)
    stream_codec_infos = [ (stream.index, CodecInfo.from_codec_context(stream.codec_context)) for stream in self._container.streams if stream.codec_context is not None ]
    # find compatible streams
    self._stream_index_map = {}
    self._transcoder_map = {}
    self._t0 = 0
    
    # assing streams to topics and create transcoders

    for topic, codec_info in topic_encodings:
      if topic in self._transcoder_map: continue
      for stream_index in range(len(stream_codec_infos)):
        if stream_index in self._stream_index_map: continue
        if codec_info.compatible_with(stream_codec_infos[stream_index][1]): 
          self._stream_index_map[stream_index] = topic
          self._transcoder_map[topic] = EmptyTranscoder()
          break

    for topic, codec_info in topic_encodings:
      if topic in self._transcoder_map: continue
      for stream_index, stream_codec_info in stream_codec_infos:
        if stream_index in self._stream_index_map: continue
        if codec_info.type == stream_codec_info.type:
          self._stream_index_map[stream_index] = topic

          in_codec_context = self._container.streams[stream_index].codec_context
          CodecOptions.apply(in_codec_context, codec_options)
          self._transcoder_map[topic] = AVTranscoder(Decoder(in_codec_context), codec_info.get_encoder())
          break

    # check is all topics have been assigned
    for topic, codec_info in topic_encodings:
      if topic not in self._transcoder_map: raise Exception(f"Could not find a compatible stream for topic {topic} with codec {codec_info.codec}")

  async def demux(self) -> AsyncIterable[tuple[int, MediaPacket]]:
    loop = asyncio.get_running_loop()
    packet_iter = await loop.run_in_executor(None, self._container.demux)
    while True:
      av_packet = await loop.run_in_executor(None, packet_iter.__next__)
      if av_packet is None: break

      if av_packet.stream_index not in self._stream_index_map: continue

      topic = self._stream_index_map[av_packet.stream_index]
      transcoder = self._transcoder_map[topic]


      if self._t0 == 0 and av_packet.pts is not None: self._t0 = int(time.time() * 1000 - (av_packet.pts / DEFAULT_TIME_BASE_TO_MS))
      packet = MediaPacket.from_av_packet(av_packet, self._t0)

      for t_packet in await transcoder.transcode(packet):
        yield (topic, t_packet) 

  def close(self):
    self._container.close()

class OutputContainer:
  _container: av.container.OutputContainer
  _stream_index_map: dict[int, int]

  def __init__(self, url_or_path: str, topic_encodings: list[tuple[int, CodecInfo]], codec_options: CodecOptions = {}, **kwargs):
    self._stream_index_map = {}
    self._container = av.open(url_or_path, "w", **kwargs)
    for topic, codec_info in topic_encodings:
      stream_idx = len(self._container.streams)
      self._stream_index_map[topic] = stream_idx
      self._container.add_stream(codec_name=codec_info.codec, rate=codec_info.framerate)
      CodecOptions.apply(self._container.streams[stream_idx].codec_context, codec_options)

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