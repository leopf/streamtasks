from pydantic import BaseModel
from streamtasks.media.packet import MediaPacket

"""
The structures are intended to be used by the system and must all have a timestamp. Timestamps are in milliseconds.
A message is clear, a packet is opaque.
"""

class TimestampMessage(BaseModel):
  timestamp: int

class IdMessage(BaseModel):
  id: str

class TimestampChuckMessage(TimestampMessage):
  data: bytes

class IdChuckMessage(IdMessage):
  data: bytes

class NumberMessage(TimestampMessage):
  timestamp: int
  value: float

class StringMessage(TimestampMessage):
  timestamp: int
  value: str

class MediaMessage(TimestampMessage):
  packets: list[MediaPacket]