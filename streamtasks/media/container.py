import dataclasses
from fractions import Fraction
import functools
import av.container
import av.stream
import av
import asyncio
from streamtasks.media.audio import AudioCodecInfo
from streamtasks.media.codec import AVTranscoder, CodecInfo, Decoder
from streamtasks.media.packet import MediaPacket
from streamtasks.media.video import VideoCodecInfo
from streamtasks.utils import AsyncTrigger

class _StreamContext:
  def __init__(self) -> None:
    self.lock = asyncio.Lock()
    self.time_base = Fraction(1, 1)
  
    self._sync_update_trigger = AsyncTrigger()
    self._sync_channels: dict[int, int] = {}
  
  def create_sync_channel(self):
    channel_id = len(self._sync_channels)
    self._sync_channels[channel_id] = 0
    return channel_id
  
  def is_min(self, channel: int): return self._sync_channels[channel] == min(self._sync_channels.values())
  
  async def sync_wait_channel_min(self, channel: int):
    while not self.is_min(channel):
      await self._sync_update_trigger.wait()

  def set_sync_channel_time(self, channel: int, time: int, time_base: Fraction):
    time = time * round(float(time_base / self.time_base))
    self._sync_channels[channel] = max(self._sync_channels[channel], time)
    self._sync_update_trigger.trigger()
    
  def add_time_base(self, time_base: Fraction): self.time_base = max(self.time_base * time_base, Fraction(1, 10_000_000)) 

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
      if packet.size == 0 and packet.dts is None and packet.pts is None: raise EOFError() # HACK: for some reason dummy packets are emittied forever after some streams
      assert packet.dts <= packet.pts, "dts must be lower than pts while demuxing"
      return MediaPacket.from_av_packet(packet)

class InputContainer:
  def __init__(self, container: av.container.InputContainer):
    self._container = container
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
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, self._container.close)

  @staticmethod
  async def open(url_or_path: str, **kwargs):
    loop = asyncio.get_running_loop()
    container = await loop.run_in_executor(None, functools.partial(av.open, url_or_path, "r", **kwargs))
    container.flags |= av.container.Flags.NOBUFFER
    return InputContainer(container)

class AVOutputStream:
  def __init__(self, ctx: _StreamContext, time_base: Fraction, stream: av.stream.Stream) -> None:
    self._stream = stream
    self._ctx = ctx
    self._time_base = time_base
    self._dts_counter = 0
    self._sync_channel = ctx.create_sync_channel()
    self._packet_len: int
    self._ctx.add_time_base(time_base)
    if stream.type == "audio": self._packet_len = stream.codec_context.frame_size
    else: self._packet_len = 1 
  
  @property
  def duration(self): return self._time_base * self._dts_counter
  
  @duration.setter
  def duration(self, duration: Fraction):
    self._dts_counter = max(self._dts_counter, int(duration / self._time_base))
    self._ctx.set_sync_channel_time(self._sync_channel, self._dts_counter, self._time_base)
  
  @property
  def ready_for_packet(self): return self._ctx.is_min(self._sync_channel)
  
  async def mux(self, packet: MediaPacket):
    packet = dataclasses.replace(packet)
    packet.dts = self._dts_counter    
    av_packet = packet.to_av_packet(self._time_base)
    av_packet.stream = self._stream 
    
    await self._ctx.sync_wait_channel_min(self._sync_channel)
    
    loop = asyncio.get_running_loop()
    async with self._ctx.lock:
      assert av_packet.dts <= av_packet.pts, "dts must be lower than pts before muxing"
      await loop.run_in_executor(None, self._stream.container.mux, av_packet)
      assert av_packet.dts <= av_packet.pts, "dts must be lower than pts after muxing"
      if self._stream.type == "audio":
        self._dts_counter += self._stream.codec_context.frame_size
      else:
        self._dts_counter += 1
      self._ctx.set_sync_channel_time(self._sync_channel, self._dts_counter, self._time_base)

class OutputContainer:
  def __init__(self, container: av.container.OutputContainer):
    self._container: av.OutputContainer = container
    self._ctx = _StreamContext()
    
  def __del__(self): self._container.close()
  
  async def close(self):
    await self._ctx.lock.acquire()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, self._container.close)
  
  def add_video_stream(self, codec_info: VideoCodecInfo):
    time_base = codec_info.time_base
    if time_base is None: raise ValueError("time_base must not be None")
    stream = self._container.add_stream(codec_name=codec_info.codec, rate=codec_info.frame_rate, width=codec_info.width, height=codec_info.height, format=codec_info.to_av_format(), options=codec_info.options) 
    return AVOutputStream(self._ctx, time_base, stream)
  
  def add_audio_stream(self, codec_info: AudioCodecInfo):
    time_base = codec_info.time_base
    if time_base is None: raise ValueError("time_base must not be None")
    stream = self._container.add_stream(codec_name=codec_info.codec, rate=codec_info.sample_rate, format=codec_info.to_av_format(), options=codec_info.options) 
    return AVOutputStream(self._ctx, time_base, stream)
  
  @staticmethod
  async def open(url_or_path: str, **kwargs):
    loop = asyncio.get_running_loop()
    container: av.OutputContainer = await loop.run_in_executor(None, functools.partial(av.open, url_or_path, "w", **kwargs)) 
    container.flags |= av.container.Flags.NOBUFFER
    return OutputContainer(container)