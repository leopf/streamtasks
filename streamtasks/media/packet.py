from dataclasses import dataclass
from fractions import Fraction
from typing import Optional
import av

@dataclass
class MediaPacket:
  data: bytes
  pts: Optional[int]
  is_keyframe: bool
  rel_dts: Optional[int]
  
  @property
  def dts(self): return self.pts - self.rel_dts if self.rel_dts is not None and self.pts is not None else None
  
  def to_av_packet(self):
    packet = av.Packet(self.data)
    packet.pts = self.pts
    packet.dts = self.dts
    return packet

  @staticmethod
  def from_av_packet(packet: av.Packet):
    rel_dts = None if packet.dts is None or packet.pts is None else packet.pts - packet.dts
    return MediaPacket(bytes(packet), packet.pts, packet.is_keyframe, rel_dts)