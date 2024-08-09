from streamtasks.message.types import TimestampMessage
from dataclasses import dataclass
from fractions import Fraction
import av

@dataclass
class MediaPacket:
  data: bytes
  pts: int
  rel_dts: int
  is_keyframe: bool

  @property
  def dts(self): return self.pts - self.rel_dts

  @dts.setter
  def dts(self, v: int): self.pts = v + self.rel_dts

  def to_av_packet(self, time_base: Fraction | None):
    packet = av.Packet(self.data)
    packet.pts = self.pts
    packet.dts = self.dts
    packet.time_base = time_base
    packet.is_keyframe = self.is_keyframe
    return packet

  @staticmethod
  def from_av_packet(packet: av.Packet, time_base: Fraction):
    if packet.time_base is None or packet.pts is None: raise ValueError("Expected time_base and pts on av.Packet!")
    time_base_factor = float(packet.time_base / time_base)
    rel_dts = int((packet.pts - (packet.dts or packet.pts)) * time_base_factor)
    pts = int(packet.pts * time_base_factor)
    return MediaPacket(bytes(packet), pts, rel_dts, packet.is_keyframe)

class MediaMessage(TimestampMessage):
  packet: MediaPacket
