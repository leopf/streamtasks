from typing import Optional
from pydantic import BaseModel

"""
The structures are intended to be used by the system and must all have a timestamp. Timestamps are in milliseconds.
A message is clear, a packet is opaque.
"""

class NumberMessage(BaseModel):
  timestamp: int
  value: float

class StringMessage(BaseModel):
  timestamp: int
  value: str

class MediaPacket:
  timestamp: int # 6 bytes
  pts: Optional[int] # 6 bytes, not sure 
  rel_dts: Optional[int] # 3 byte cause time base...
  is_keyframe: bool # 1 byte
  data: bytes # variable length + 4

  def __init__(self, data: bytes, timestamp: int, pts: Optional[int], is_keyframe: bool, rel_dts: Optional[int]=None):
    self.timestamp = timestamp
    self.pts = pts
    self.rel_dts = rel_dts
    self.is_keyframe = is_keyframe
    self.data = data  

  @property
  def dts(self): return self.pts - self.rel_dts if self.rel_dts is not None and self.pts is not None else None
  @property
  def size(self): return len(self.data) + 20
  def as_dict(self): return self.__dict__
  @staticmethod
  def from_dict(d: dict): return MediaPacket(**d)