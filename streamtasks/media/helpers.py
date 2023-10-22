from streamtasks.media.config import DEFAULT_TIME_BASE, DEFAULT_TIME_BASE_TO_MS
import av

from streamtasks.message.structures import MediaPacket


def av_packet_to_media_packat(packet: av.Packet, t0: int):
  timestamp = 0 if t0 == 0 or packet.pts is None else t0 + int(packet.pts / DEFAULT_TIME_BASE_TO_MS)
  rel_dts = None if packet.dts is None or packet.pts is None else packet.pts - packet.dts
  return MediaPacket(bytes(packet), timestamp, packet.pts, packet.is_keyframe, rel_dts)


def media_packet_to_av_packet(media_packet: MediaPacket):
  packet = av.Packet(media_packet.data)
  packet.pts = media_packet.pts
  packet.dts = media_packet.dts
  packet.time_base = DEFAULT_TIME_BASE
  return packet