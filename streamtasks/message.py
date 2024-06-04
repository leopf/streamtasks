from pydantic import BaseModel
from streamtasks.media.packet import MediaPacket

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

class TextMessage(TimestampMessage):
  timestamp: int
  value: str

class MediaMessage(TimestampMessage):
  packet: MediaPacket
