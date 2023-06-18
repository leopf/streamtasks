import unittest
from streamtasks.media.video import VideoCodecInfo, VideoFrame
from streamtasks.media.types import MediaPacket
import numpy as np

class TestCodec(unittest.IsolatedAsyncioTestCase):
  w = 480
  h = 360

  def generate_frames(self, frame_count):
    h = self.h
    w = self.w
    for i in range(frame_count):
      arr = np.zeros((h, w, 3), dtype=np.uint8)
      # draw 40x40 square at (i, i)
      y = i % (h - 40)
      x = i % (w - 40)
      arr[y:y+40, x:x+40] = 255
      yield arr

  def get_video_codec(self, crf, codec='h264', pixel_format='yuv420p'):
    return VideoCodecInfo(self.w, self.h, 1, crf=crf, codec=codec, pixel_format=pixel_format)

  def normalize_video_frame(self, frame: VideoFrame):
    np_frame = frame.to_rgb().to_ndarray()
    # remove alpha channel from argb
    np_frame = np_frame[:, :, :3]
    # round frame to 0 or 255
    np_frame = np.where(np_frame > 127, 255, 0)
    return np_frame

  async def test_inverse_transcoder(self):
    frame_count = 100

    codec = self.get_video_codec(crf=0)
    encoder = codec.get_encoder()
    decoder = codec.get_decoder()

    created_frames = []
    for frame in self.generate_frames(frame_count):
      created_frames.append(frame)
      encoded = await encoder.encode(VideoFrame.from_ndarray(frame, 'rgb24'))
      for p in encoded:
        decoded: list[VideoFrame] = await decoder.decode(p)
        for d in decoded:
          self.assertTrue(np.array_equal(self.normalize_video_frame(d), created_frames.pop(0)))
    self.assertLess(len(created_frames), frame_count) # make sure we actually tested something

  async def test_transcoder(self):
    frame_count = 100
    codec1 = self.get_video_codec(crf=0)
    codec2 = self.get_video_codec(crf=0, codec='libvpx-vp9', pixel_format='yuv420p')
    transcoder = codec1.get_transcoder(codec2)
    encoder = codec1.get_encoder()
    decoder = codec2.get_decoder()

    created_frames = []
    for frame in self.generate_frames(frame_count):
      created_frames.append(frame)
      e_packets: list[MediaPacket] = await encoder.encode(VideoFrame.from_ndarray(frame, 'rgb24'))
      for e_p in e_packets:
        t_packets: list[MediaPacket] = await transcoder.transcode(e_p)
        for t_p in t_packets:
          decoded: list[VideoFrame] = await decoder.decode(t_p)
          for d in decoded:
            decoded_frame = self.normalize_video_frame(d)
            self.assertTrue(np.array_equal(decoded_frame, created_frames.pop(0)))
    self.assertLess(len(created_frames), frame_count) # make sure we actually tested something

if __name__ == '__main__':
  unittest.main()
