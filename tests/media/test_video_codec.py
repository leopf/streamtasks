import unittest
from streamtasks.media.packet import MediaPacket
from streamtasks.media.video import VideoCodecInfo
import numpy as np
from tests.media import decode_all_packets, decode_video_packets, encode_all_frames, generate_media_frames, normalize_video_frame

class TestVideoCodec(unittest.IsolatedAsyncioTestCase):
  w = 480
  h = 360
  frame_count = 100

  def get_video_codec(self, codec='h264', pixel_format='yuv420p'): return VideoCodecInfo(self.w, self.h, 1, codec=codec, pixel_format=pixel_format)

  async def test_inverse_transcoder(self):
    codec = self.get_video_codec()
    frames, in_frames = generate_media_frames(codec, self.frame_count)
    packets = await encode_all_frames(codec.get_encoder(), frames)
    out_frames = await decode_video_packets(codec, packets)
    self.assertGreater(len(out_frames), 0)
    for a, b in zip(in_frames, out_frames): self.assertTrue(np.array_equal(a, b))

  async def test_transcoder(self):
    codec1 = self.get_video_codec()
    codec2 = self.get_video_codec(codec='libvpx-vp9', pixel_format='yuv420p')
    transcoder = codec1.get_transcoder(codec2)
    frames, in_frames = generate_media_frames(codec1, self.frame_count)
    packets = await encode_all_frames(codec1.get_encoder(), frames)
    
    t_packets: list[MediaPacket] = []
    for packet in packets: t_packets.extend(await transcoder.transcode(packet))
    t_packets.extend(await transcoder.flush())
    
    out_frames = await decode_video_packets(codec2, t_packets)
    self.assertGreater(len(out_frames), 0)
    for a, b in zip(in_frames, out_frames): self.assertTrue(np.array_equal(a, b))

if __name__ == '__main__':
  unittest.main()
