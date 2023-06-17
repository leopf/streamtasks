from dataclasses import dataclass
from streamtasks.media.config import *
import av

class StreamPacket:
  timestamp_ms: int # 6 bytes

  def __init__(self, timestamp_ms: int):
    self.timestamp_ms = timestamp_ms

class NumberPacket(StreamPacket):
  value: float() # 4 bytes

  def __init__(self, value: float, timestamp_ms: int):
    super().__init__(timestamp_ms)
    self.value = value

class MediaPacket(StreamPacket):
  pts: int # 6 bytes, not sure 
  rel_dts: int # 3 byte cause time base...
  is_keyframe: bool # 1 byte
  data: bytes # variable length + 4

  def __init__(self, data: bytes, timestamp_ms: int, pts: int, is_keyframe: bool, rel_dts: int=0):
    super().__init__(timestamp_ms)
    self.pts = pts
    self.rel_dts = rel_dts
    self.is_keyframe = is_keyframe
    self.data = data  

  @property
  def dts(self): return self.pts - self.rel_dts

  @property
  def size(self): return len(self.data) + 20

  def to_av_packet(self):
    packet = av.Packet(self.data)
    packet.pts = self.pts
    packet.dts = self.dts
    packet.time_base = DEFAULT_TIME_BASE
    return packet

  @staticmethod
  def from_av_packet(packet: av.Packet, t0: int):
    return MediaPacket(packet.to_bytes(), t0 + int(packet.pts / DEFAULT_TIME_BASE_TO_MS), packet.pts, packet.is_keyframe, packet.pts - packet.dts)
