import dataclasses
from fractions import Fraction
import av.stream
import av.video
import av
import asyncio
from streamtasks.media.audio import AudioCodecInfo
from streamtasks.media.codec import AVTranscoder, CodecInfo, Decoder
from streamtasks.media.packet import MediaPacket
from streamtasks.media.video import VideoCodecInfo

class AVInputStream:
  def __init__(self, demux_lock: asyncio.Lock, stream: av.stream.Stream, transcode: bool) -> None:
    self._stream = stream
    self._demux_lock = demux_lock
    self._transcoder: None | AVTranscoder = None
    if transcode:
      codec_info = self.codec_info
      self._transcoder = AVTranscoder(Decoder(stream.codec_context, codec_info.time_base), codec_info.get_encoder())
    
  @property
  def codec_info(self) -> CodecInfo: return CodecInfo.from_codec_context(self._stream.codec_context)

  async def demux(self) -> list[MediaPacket]:
    loop = asyncio.get_event_loop()
    async with self._demux_lock:
      packet = await loop.run_in_executor(None, self._demux)
      if packet is None: return []
      if self._transcoder is not None: return await self._transcoder.transcode(packet)
      else: return [ packet ]
  
  def _demux(self):
    for packet in self._stream.container.demux(self._stream):
      return MediaPacket.from_av_packet(packet)

  def _demux(self):
    for packet in self._stream.container.demux(self._stream):
      return MediaPacket.from_av_packet(packet)

class InputContainer:
  def __init__(self, url_or_path: str, **kwargs):
    self._container = av.open(url_or_path, "r", **kwargs)
    self._demux_lock = asyncio.Lock()
  
  def __del__(self): self._container.close()
  
  def get_video_stream(self, idx: int, transcode: bool):
    av_stream = self._container.streams.video[idx]
    return AVInputStream(self._demux_lock, av_stream, transcode)
  
  def get_audio_stream(self, idx: int, transcode: bool):
    av_stream = self._container.streams.audio[idx]
    return AVInputStream(self._demux_lock, av_stream, transcode)
  
  async def close(self):
    await self._demux_lock.acquire()
    self._container.close()

class AVOutputStream:
  def __init__(self, mux_lock: asyncio.Lock, time_base: Fraction, stream: av.stream.Stream) -> None:
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
    return AVOutputStream(self._mux_lock, time_base, stream)
  
  def add_audio_stream(self, codec_info: AudioCodecInfo):
    time_base = codec_info.time_base
    if time_base is None: raise ValueError("time_base must not be None")
    stream = self._container.add_stream(codec_name=codec_info.codec, rate=codec_info.sample_rate, format=codec_info.to_av_format(), options=codec_info.options) 
    return AVOutputStream(self._mux_lock, time_base, stream)