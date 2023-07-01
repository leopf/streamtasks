from dataclasses import dataclass
from streamtasks.media.config import *
import av
from typing import Optional

class StreamPacket:
  timestamp: int # 6 bytes

  def __init__(self, timestamp: int):
    self.timestamp = timestamp

class NumberPacket(StreamPacket):
  value: float # 4 bytes

  def __init__(self, value: float, timestamp: int):
    super().__init__(timestamp)
    self.value = value

class MediaPacket(StreamPacket):
  pts: Optional[int] # 6 bytes, not sure 
  rel_dts: Optional[int] # 3 byte cause time base...
  is_keyframe: bool # 1 byte
  data: bytes # variable length + 4

  def __init__(self, data: bytes, timestamp: int, pts: Optional[int], is_keyframe: bool, rel_dts: Optional[int]=None):
    super().__init__(timestamp)
    self.pts = pts
    self.rel_dts = rel_dts
    self.is_keyframe = is_keyframe
    self.data = data  

  @property
  def dts(self): return self.pts - self.rel_dts if self.rel_dts is not None and self.pts is not None else None

  @property
  def size(self): return len(self.data) + 20
