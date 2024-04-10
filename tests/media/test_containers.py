import os
import tempfile
import unittest
from streamtasks.media.audio import AudioCodecInfo, AudioFrame
from streamtasks.media.container import InputContainer, OutputContainer
from streamtasks.media.video import VideoCodecInfo, VideoFrame
from tests.media import create_audio_samples, create_audio_track, generate_frames, normalize_video_frame
import numpy as np
import scipy


class TestContainers(unittest.IsolatedAsyncioTestCase):
  def setUp(self) -> None:
    self.container_filename = tempfile.mktemp()
  
  def tearDown(self) -> None:
    os.remove(self.container_filename)
  
  async def test_mp4_video_container(self): await self._test_codef_format_video_io_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "h264"), "mp4")
  async def test_webm_video_container(self): await self._test_codef_format_video_io_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "h264"), "webm")
  
  async def _test_codef_format_video_io_container(self, codec: VideoCodecInfo, format: str):
    w = codec.width
    h = codec.height
      
    output_container = OutputContainer(self.container_filename, format="mp4")
    out_video_stream = output_container.add_video_stream(codec)
    encoder = codec.get_encoder()
    frames = list(generate_frames(w, h, 120))
    for frame in frames:
      for packet in await encoder.encode(VideoFrame.from_ndarray(frame, "rgb24").convert(pixel_format=codec.pixel_format)):
        await out_video_stream.mux(packet)
        
    for packet in await encoder.flush():
      await out_video_stream.mux(packet)
        
    encoder.close()
    await output_container.close()
    
    input_container = InputContainer(self.container_filename, format="mp4", options={ "bufsize": "0" })
    in_video_stream = input_container.get_video_stream(0, True) # TODO: the goal is to set transcode to false in this case
    in_codec = in_video_stream.codec_info
    self.assertTrue(codec.compatible_with(in_codec))
    
    decoder = codec.get_decoder()
    decoded_frames = []

    with self.assertRaises(EOFError):
      while True:
        packets = await in_video_stream.demux()
        for packet in packets:
          for frame in await decoder.decode(packet):
            decoded_frames.append(normalize_video_frame(frame))

    flushed_frames = 0 # flushed frames may be scuffed
    for frame in await decoder.flush():
      flushed_frames += 1
      decoded_frames.append(normalize_video_frame(frame))

    print("Decoded frames: {}".format(len(decoded_frames)))
    self.assertGreater(len(decoded_frames), 0)
    for idx, (a, b) in enumerate(zip(decoded_frames[:-flushed_frames], frames)):
      self.assertTrue(np.array_equal(a, b))
      
    await input_container.close()

if __name__ == '__main__':
  unittest.main()
