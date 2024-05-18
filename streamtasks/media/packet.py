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

  @dts.setter
  def dts(self, v: int):
    if self.pts is None:
      self.pts = v
      self.rel_dts = 0
    if self.rel_dts is None: self.rel_dts = 0
    self.pts = v + self.rel_dts

  def to_av_packet(self, time_base: Fraction | None):
    packet = av.Packet(self.data)
    packet.pts = self.pts
    packet.dts = self.dts
    packet.time_base = time_base
    packet.is_keyframe = self.is_keyframe
    return packet

  @staticmethod
  def from_av_packet(packet: av.Packet, time_base: Fraction):
    if packet.time_base is None or packet.pts is None:
      rel_dts = None
      pts = None
    else:
      time_base_factor = float(packet.time_base / time_base)
      rel_dts = int((packet.pts - packet.dts) * time_base_factor)
      pts = int(packet.pts * time_base_factor)
    return MediaPacket(bytes(packet), pts, packet.is_keyframe, rel_dts)
