import dataclasses
from fractions import Fraction
import av.video
import av
import asyncio

from streamtasks.media.packet import MediaPacket
from streamtasks.media.video import VideoCodecInfo


# class InputContainer:
#   _container: av.container.InputContainer
#   _transcoder_map: dict[int, Transcoder]
#   _stream_index_map: dict[int, int]

#   def __init__(self, url: str, topic_encodings: list[tuple[int, CodecInfo]], codec_options: CodecOptions = {}, **kwargs):
#     self._container = av.open(url, "r", **kwargs)
#     stream_codec_infos = [ (stream.index, CodecInfo.from_codec_context(stream.codec_context)) for stream in self._container.streams if stream.codec_context is not None ]
#     # find compatible streams
#     self._stream_index_map = {}
#     self._transcoder_map = {}

#     # assing streams to topics and create transcoders

#     for topic, codec_info in topic_encodings:
#       if topic in self._transcoder_map: continue
#       for stream_index in range(len(stream_codec_infos)):
#         if stream_index in self._stream_index_map: continue
#         if codec_info.compatible_with(stream_codec_infos[stream_index][1]):
#           self._stream_index_map[stream_index] = topic
#           self._transcoder_map[topic] = EmptyTranscoder()
#           break

#     for topic, codec_info in topic_encodings:
#       if topic in self._transcoder_map: continue
#       for stream_index, stream_codec_info in stream_codec_infos:
#         if stream_index in self._stream_index_map: continue
#         if codec_info.type == stream_codec_info.type:
#           self._stream_index_map[stream_index] = topic

#           in_codec_context = self._container.streams[stream_index].codec_context
#           self._transcoder_map[topic] = AVTranscoder(Decoder(in_codec_context), codec_info.get_encoder())
#           break

#     # check is all topics have been assigned
#     for topic, codec_info in topic_encodings:
#       if topic not in self._transcoder_map: raise Exception(f"Could not find a compatible stream for topic {topic} with codec {codec_info.codec}")

#   async def demux(self) -> AsyncIterable[tuple[int, MediaPacket]]:
#     loop = asyncio.get_running_loop()
#     packet_iter = await loop.run_in_executor(None, self._container.demux)
#     while True:
#       av_packet = await loop.run_in_executor(None, packet_iter.__next__)
#       if av_packet is None: break

#       if av_packet.stream_index not in self._stream_index_map: continue

#       topic = self._stream_index_map[av_packet.stream_index]
#       transcoder = self._transcoder_map[topic]

#       packet = MediaPacket.from_av_packet(av_packet)

#       for t_packet in await transcoder.transcode(packet):
#         yield (topic, t_packet)

#   def close(self):
#     self._container.close()

class VideoInputStream:
  def __init__(self, demux_lock: asyncio.Lock, stream: av.video.VideoStream) -> None:
    self._stream = stream
    self._demux_lock = demux_lock
  
  @property
  def codec_info(self): return VideoCodecInfo.from_codec_context(self._stream.codec_context)
  
  async def demux(self):
    loop = asyncio.get_event_loop()
    async with self._demux_lock:
      return await loop.run_in_executor(None, self._demux)

  def _demux(self):
    for packet in self._stream.container.demux(self._stream):
      return MediaPacket.from_av_packet(packet)

class InputContainer:
  def __init__(self, url_or_path: str, **kwargs):
    self._container = av.open(url_or_path, "r", **kwargs)
    self._demux_lock = asyncio.Lock()
  
  def __del__(self): self._container.close()
  
  def get_video_stream(self, idx: int):
    av_stream = self._container.streams.video[idx]
    return VideoInputStream(self._demux_lock, av_stream)
  
  async def close(self):
    await self._demux_lock.acquire()
    self._container.close()

class VideoOutputStream:
  def __init__(self, mux_lock: asyncio.Lock, time_base: Fraction, stream: av.video.VideoStream) -> None:
    self._stream = stream
    self._mux_lock = mux_lock
    self._time_base = time_base
    self._dts_counter = 0
    
  async def mux(self, packet: MediaPacket):
    packet = dataclasses.replace(packet)
    packet.dts = self._dts_counter
    self._dts_counter += 1
    av_packet = packet.to_av_packet(self._time_base)
    loop = asyncio.get_running_loop()
    async with self._mux_lock:
      await loop.run_in_executor(None, self._stream.container.mux, av_packet)

class OutputContainer:
  def __init__(self, url_or_path: str, **kwargs):
    self._container: av.container.OutputContainer = av.open(url_or_path, "w", **kwargs)
    self._mux_lock = asyncio.Lock()
    
  def __del__(self): self._container.close()
  
  async def close(self):
    await self._mux_lock.acquire()
    self._container.close()
  
  def add_video_stream(self, codec_info: VideoCodecInfo):
    time_base = codec_info.time_base
    if time_base is None: raise ValueError("time_base must not be None")
    stream = self._container.add_stream(codec_name=codec_info.codec, rate=codec_info.frame_rate, width=codec_info.width, height=codec_info.height, format=codec_info.to_av_format(), options=codec_info.options) 
    return VideoOutputStream(self._mux_lock, time_base, stream)