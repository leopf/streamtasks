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
from streamtasks.utils import AsyncConsumer, AsyncMPProducer, AsyncProducer, AsyncTrigger

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

class _Demuxer(AsyncMPProducer[av.Packet]):
  def __init__(self, container: av.container.InputContainer) -> None:
    super().__init__()
    self.container = container
  
  def run_sync(self):
    for av_packet in self.container.demux():
      if av_packet.size == 0 and av_packet.dts is None and av_packet.pts is None: break # HACK: for some reason dummy packets are emittied forever after some streams
      assert av_packet.dts <= av_packet.pts, "dts must be lower than pts while demuxing"    
      self.send_message(av_packet)
      if self.stop_event.is_set(): return
    self.close_all()

class StreamConsumer(AsyncConsumer[av.Packet]):
  def __init__(self, producer: AsyncProducer, stream_index: int) -> None:
    super().__init__(producer)
    self._stream_index = stream_index  
  def test_message(self, message: av.Packet) -> bool: return self._stream_index == message.stream_index

class AVInputStream:
  def __init__(self, demuxer: _Demuxer, stream: av.stream.Stream, target_codec: CodecInfo, force_transcode: bool) -> None:
    self._stream = stream
    self._transcoder: None | AVTranscoder = None
    self._consumer = StreamConsumer(demuxer, stream.index)
    self._consumer.register()
    self._time_base = target_codec.time_base
    try:
      codec_info = CodecInfo.from_codec_context(self._stream.codec_context)
      if force_transcode or not target_codec.compatible_with(codec_info):
        # TODO format conversion and resampling!!
        self._transcoder = AVTranscoder(Decoder(stream.codec_context, codec_info.time_base), target_codec.get_encoder())
    except TypeError: pass # NOTE: some contexts dont have all the codec info
    
  @property
  def codec_info(self) -> CodecInfo: return CodecInfo.from_codec_context(self._stream.codec_context)

  def convert_position(self, position: int, target_time: Fraction): return int((self._time_base * position) / target_time)

  async def demux(self) -> list[MediaPacket]:
    try:
      av_packet = await self._consumer.get()
      time_base_factor = float(self._time_base / av_packet.time_base)
      packet = MediaPacket.from_av_packet(av_packet)
      packet.rel_dts = int((packet.pts - packet.dts) / time_base_factor)
      packet.pts = int(packet.pts / time_base_factor)
      if self._transcoder is not None: return await self._transcoder.transcode(packet)
      else: return [ packet ]
    except EOFError:
      if self._transcoder is None or self._transcoder.flushed: raise
      return await self._transcoder.flush()

class InputContainer:
  def __init__(self, container: av.container.InputContainer):
    self._container = container
    self._demuxer = _Demuxer(container)
  
  def __del__(self): self._container.close()
  
  def get_video_stream(self, idx: int, target_codec: VideoCodecInfo, force_transcode: bool = False):
    av_stream = self._container.streams.video[idx]
    stream = AVInputStream(self._demuxer, av_stream, target_codec, force_transcode)
    return stream
    
  def get_audio_stream(self, idx: int, target_codec: AudioCodecInfo, force_transcode: bool = False):
    av_stream = self._container.streams.audio[idx]
    stream = AVInputStream(self._demuxer, av_stream, target_codec, force_transcode)
    return stream
  
  async def close(self):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, self._container.close)

  @staticmethod
  async def open(url_or_path: str, **kwargs):
    loop = asyncio.get_running_loop()
    container: av.container.InputContainer = await loop.run_in_executor(None, functools.partial(av.open, url_or_path, "r", **kwargs))
    container.flags |= av.container.Flags.NOBUFFER
    return InputContainer(container)

class AVOutputStream:
  def __init__(self, ctx: _StreamContext, time_base: Fraction, stream: av.stream.Stream) -> None:
    self._stream = stream
    self._ctx = ctx
    self._time_base = time_base
    self._dts_counter = 0
    self._sync_channel = ctx.create_sync_channel()
    self._ctx.add_time_base(time_base)
  
  @property
  def duration(self): return self._time_base * self._dts_counter
  
  @duration.setter
  def duration(self, duration: Fraction):
    if int(duration / self._time_base) > self._dts_counter: print(f"set duration {self._stream.type}")
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
    stream = self._container.add_stream(codec_name=codec_info.codec, rate=codec_info.sample_rate, channels=codec_info.channels, format=codec_info.to_av_format(), options=codec_info.options) 
    return AVOutputStream(self._ctx, time_base, stream)
  
  @staticmethod
  async def open(url_or_path: str, **kwargs):
    loop = asyncio.get_running_loop()
    container: av.OutputContainer = await loop.run_in_executor(None, functools.partial(av.open, url_or_path, "w", **kwargs)) 
    container.flags |= av.container.Flags.NOBUFFER
    return OutputContainer(container)