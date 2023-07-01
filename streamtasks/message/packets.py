from typing import Optional

"""
Packets must all have a timestamp.
"""

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