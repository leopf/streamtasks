from dataclasses import dataclass

@dataclass
class MediaPacket:
    data: bytes
    timestamp: int