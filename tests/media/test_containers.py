import asyncio
import os
import tempfile
import unittest
from streamtasks.media.audio import AudioCodecInfo, AudioFrame, AudioResampler
from streamtasks.media.codec import Decoder
from streamtasks.media.container import InputContainer, OutputContainer
from streamtasks.media.video import VideoCodecInfo, VideoFrame
from tests.media import create_audio_samples, create_audio_track, generate_frames, get_freq_similarity, get_spectum, normalize_video_frame
import numpy as np
import scipy

from tests.shared import full_test


class TestContainers(unittest.IsolatedAsyncioTestCase):
  def setUp(self) -> None:
    self.container_filename = tempfile.mktemp()
  
  def tearDown(self) -> None:
    os.remove(self.container_filename)
  
  async def test_mp4_h264_video_container(self): await self._test_codec_format_video_io_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "h264"), "mp4", True)
  @full_test
  async def test_mp4_h265_video_container(self): await self._test_codec_format_video_io_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "hevc"), "mp4", True)
  @full_test
  async def test_webm_video_container(self): await self._test_codec_format_video_io_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "vp8"), "webm", False)
  
  async def test_mp4_1_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("aac", 2, 32000, "fltp"), "mp4", False)
  @full_test
  async def test_mp4_2_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("aac", 1, 16000, "fltp"), "mp4", False)
  @full_test
  async def test_wav_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("pcm_s16le", 1, 16000, "s16"), "wav", False)
  @full_test
  async def test_flac_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("flac", 1, 16000, "s16"), "flac", False)
  
  async def _test_codec_format_audio_io_container(self, codec: AudioCodecInfo, format: str, transcode: bool):
    output_container = OutputContainer(self.container_filename, format=format)
    out_audio_stream = output_container.add_audio_stream(codec)
    encoder = codec.get_encoder()
    in_samples = create_audio_track(10, codec.sample_rate)
    resampler = codec.get_resampler()
    complete_frame = AudioFrame.from_ndarray(in_samples[np.newaxis,:], "s16", 1, codec.sample_rate)
    frames = await resampler.resample(complete_frame)
    
    for frame in frames:
      for packet in await encoder.encode(frame):
        await out_audio_stream.mux(packet)
        
    for packet in await encoder.flush():
      await out_audio_stream.mux(packet)
        
    encoder.close()
    await output_container.close()
    
    input_container = InputContainer(self.container_filename, format=format)
    in_audio_stream = input_container.get_audio_stream(0, transcode) # TODO: the goal is to set transcode to false in this case
    if transcode:
      in_codec = in_audio_stream.codec_info
      self.assertTrue(codec.compatible_with(in_codec))
   
    decoder = codec.get_decoder() # Decoder(in_audio_stream._stream.codec_context, codec.time_base)
    out_samples = []

    validation_codec = AudioCodecInfo("pcm_s16le", codec.channels, codec.sample_rate, "s16")
    validation_resampler = validation_codec.get_resampler()
  
    with self.assertRaises(EOFError):
      while True:
        for packet in await in_audio_stream.demux():
          for frame in await decoder.decode(packet):
            for frame in await validation_resampler.resample(frame):
              out_samples.append(frame.to_ndarray())

    flushed_frames = 0 # flushed frames may be scuffed
    try:
      for frame in await decoder.flush():
        flushed_frames += 1
        for frame in await validation_resampler.resample(frame):
          out_samples.append(frame.to_ndarray())
    except EOFError: pass
      
    await input_container.close()
    
    out_samples = np.concatenate(out_samples, axis=1)[0]
    similarity = get_freq_similarity(get_spectum(in_samples), get_spectum(out_samples)) # lower is better
    self.assertLess(similarity, 70)
  
  async def _test_codec_format_video_io_container(self, codec: VideoCodecInfo, format: str, transcode: bool):
    w = codec.width
    h = codec.height
      
    output_container = OutputContainer(self.container_filename, format=format)
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
    
    input_container = InputContainer(self.container_filename, format=format)
    in_video_stream = input_container.get_video_stream(0, transcode) # TODO: the goal is to set transcode to false in this case
    if transcode:
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
    try:
      for frame in await decoder.flush():
        flushed_frames += 1
        decoded_frames.append(normalize_video_frame(frame))
    except EOFError: pass

    print("Decoded frames: {}".format(len(decoded_frames)))
    self.assertGreater(len(decoded_frames), 0)
    for idx, (a, b) in enumerate(zip(decoded_frames[:-flushed_frames], frames)):
      self.assertTrue(np.array_equal(a, b))
      
    await input_container.close()

if __name__ == '__main__':
  unittest.main()
