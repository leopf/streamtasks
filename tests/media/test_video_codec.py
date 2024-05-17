import unittest

import av
from streamtasks.media.packet import MediaPacket
from streamtasks.media.video import VideoCodecInfo, copy_av_video_frame
import numpy as np
from tests.media import decode_video_packets, encode_all_frames, generate_frames, generate_media_frames

class TestVideoCodec(unittest.IsolatedAsyncioTestCase):
  w = 480
  h = 360
  frame_count = 100

  def test_copy_frame(self):
    arr = next(generate_frames(1280, 720, 1))
    frame = av.VideoFrame.from_ndarray(arr)
    c_frame = copy_av_video_frame(frame)
    
    self.assertEqual(len(frame.planes), len(c_frame.planes))
    for a, b in zip(frame.planes, c_frame.planes):
      self.assertNotEqual(a.buffer_ptr, b.buffer_ptr)

    self.assertTrue(np.array_equal(frame.to_ndarray(), c_frame.to_ndarray()))

  async def test_inverse_transcoder(self):
    codec = VideoCodecInfo(self.w, self.h, 1, codec="h264", pixel_format="yuv420p")
    frames, in_frames = generate_media_frames(codec, self.frame_count)
    packets = await encode_all_frames(codec.get_encoder(), frames)
    out_frames = await decode_video_packets(codec, packets)
    self.assertGreater(len(out_frames), 0)
    for a, b in zip(in_frames, out_frames): self.assertTrue(np.array_equal(a, b))

  async def test_transcoder_h264_2_vp9_1(self):
    codec1 = VideoCodecInfo(self.w, self.h, 1, codec="h264", pixel_format="yuv420p")
    codec2 = VideoCodecInfo(self.w, self.h, 1, codec="libvpx-vp9", pixel_format="yuv420p")
    await self._test_transcoder(codec1, codec2)
    
  async def test_transcoder_h264_2_vp9_2(self):
    codec1 = VideoCodecInfo(self.w, self.h, 2, codec="h264", pixel_format="yuv420p")
    codec2 = VideoCodecInfo(self.w, self.h, 1, codec="libvpx-vp9", pixel_format="yuv420p")
    await self._test_transcoder(codec1, codec2)
    
  async def _test_transcoder(self, codec1: VideoCodecInfo, codec2: VideoCodecInfo):
    transcoder = codec1.get_transcoder(codec2)
    frames, in_frames = generate_media_frames(codec1, self.frame_count)
    packets = await encode_all_frames(codec1.get_encoder(), frames)
    
    t_packets: list[MediaPacket] = []
    for packet in packets: t_packets.extend(await transcoder.transcode(packet))
    t_packets.extend(await transcoder.flush())
    
    out_frames = await decode_video_packets(codec2, t_packets)
    self.assertLessEqual(len(out_frames), (codec1.rate / codec2.rate) * len(in_frames), "resampling not working")
    
    self.assertGreater(len(out_frames), 0)
    if codec1.rate == codec2.rate: # TODO write a time independent test
      for a, b in zip(in_frames, out_frames): self.assertTrue(np.array_equal(a, b))

if __name__ == '__main__':
  unittest.main()
