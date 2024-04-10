import unittest
from streamtasks.media.packet import MediaPacket
from streamtasks.media.video import VideoCodecInfo, VideoFrame
import numpy as np

from tests.media import generate_frames, normalize_video_frame

class TestVideoCodec(unittest.IsolatedAsyncioTestCase):
  w = 480
  h = 360

  def get_video_codec(self, codec='h264', pixel_format='yuv420p'):
    return VideoCodecInfo(self.w, self.h, 1, codec=codec, pixel_format=pixel_format)

  async def test_inverse_transcoder(self):
    frame_count = 100

    codec = self.get_video_codec()
    encoder = codec.get_encoder()
    decoder = codec.get_decoder()

    created_frames = []
    for frame in generate_frames(self.w, self.h, frame_count):
      created_frames.append(frame)
      encoded = await encoder.encode(VideoFrame.from_ndarray(frame, 'rgb24'))
      for p in encoded:
        decoded: list[VideoFrame] = await decoder.decode(p)
        for d in decoded:
          self.assertTrue(np.array_equal(normalize_video_frame(d), created_frames.pop(0)))
    self.assertLess(len(created_frames), frame_count) # make sure we actually tested something

  async def test_transcoder(self):
    frame_count = 100
    codec1 = self.get_video_codec()
    codec2 = self.get_video_codec(codec='libvpx-vp9', pixel_format='yuv420p')
    transcoder = codec1.get_transcoder(codec2)
    encoder = codec1.get_encoder()
    decoder = codec2.get_decoder()

    created_frames = []
    for frame in generate_frames(self.w, self.h, frame_count):
      created_frames.append(frame)
      e_packets: list[MediaPacket] = await encoder.encode(VideoFrame.from_ndarray(frame, 'rgb24'))
      for e_p in e_packets:
        t_packets: list[MediaPacket] = await transcoder.transcode(e_p)
        for t_p in t_packets:
          decoded: list[VideoFrame] = await decoder.decode(t_p)
          for d in decoded:
            decoded_frame = normalize_video_frame(d)
            self.assertTrue(np.array_equal(decoded_frame, created_frames.pop(0)))
    self.assertLess(len(created_frames), frame_count) # make sure we actually tested something


if __name__ == '__main__':
  unittest.main()
