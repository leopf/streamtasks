import asyncio
from fractions import Fraction
import os
import tempfile
import unittest
from streamtasks.media.audio import AudioCodecInfo, AudioFrame, AudioResampler
from streamtasks.media.codec import Decoder
from streamtasks.media.container import AVInputStream, AVOutputStream, InputContainer, OutputContainer
from streamtasks.media.video import VideoCodecInfo, VideoFrame
from tests.media import frame_box_size_value, create_audio_track, generate_frames, get_freq_similarity, get_spectum, normalize_video_frame
import numpy as np
import scipy

from tests.shared import async_timeout, full_test


class TestContainers(unittest.IsolatedAsyncioTestCase):
  def setUp(self) -> None:
    self.container_filename = tempfile.mktemp()
  
  def tearDown(self) -> None:
    os.remove(self.container_filename)
  
  async def test_mp4_h264_video_container(self): await self._test_codec_format_video_io_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "h264"), "mp4", True)
  @full_test
  async def test_mp4_h265_video_container(self): await self._test_codec_format_video_io_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "hevc"), "mp4", True)
  
  @unittest.skip("Not working right now :)")
  @full_test
  async def test_webm_video_container(self): await self._test_codec_format_video_io_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "vp8"), "webm", False)
  
  async def test_mp4_1_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("aac", 2, 32000, "fltp"), "mp4", False)
  @full_test
  async def test_mp4_2_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("aac", 1, 16000, "fltp"), "mp4", False)
  @full_test
  async def test_wav_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("pcm_s16le", 1, 16000, "s16"), "wav", False)
  @full_test
  async def test_flac_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("flac", 1, 16000, "s16"), "flac", False)
  
  @unittest.skip("not working just yet")
  async def test_mp4_av_container_basic(self): await self._test_mp4_av_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "h264"), AudioCodecInfo("aac", 2, 32000, "fltp"))
  
  # @async_timeout(10)
  async def _test_mp4_av_container(self, video_codec: VideoCodecInfo, audio_codec: AudioCodecInfo):
    output_container = OutputContainer(self.container_filename, format="mp4")
    in_tasks = (
      asyncio.create_task(self.out_container_write_audio(output_container.add_audio_stream(audio_codec), audio_codec)),
      asyncio.create_task(self.out_container_write_video(output_container.add_video_stream(video_codec), video_codec))
    )
    _, pending = await asyncio.wait(in_tasks, return_when="FIRST_COMPLETED")
    for p in pending: p.cancel()
    in_samples, in_frames = await in_tasks[0], await in_tasks[1]
    await output_container.close()
    
    input_container = InputContainer(self.container_filename, format="mp4")
    out_tasks = (
      asyncio.create_task(self.in_container_read_audio(input_container.get_audio_stream(0, False), audio_codec, False)),
      asyncio.create_task(self.in_container_read_video(input_container.get_video_stream(0, True), video_codec, True))
    )
    await asyncio.wait(out_tasks, return_when="FIRST_COMPLETED")
    out_samples, out_frames = out_tasks[0].result(), out_tasks[1].result()
    await input_container.close()
    
    print("Decoded frames: {}".format(len(out_frames)))
    self.assertGreater(len(out_frames), 0)
    for a, b in zip(out_frames, in_frames):
      self.assertLess(np.abs(a-b).sum(), frame_box_size_value * 0.01) # allow for 1% error

    audio_similarity = get_freq_similarity(get_spectum(in_samples), get_spectum(out_samples)) # lower is better
    self.assertLess(audio_similarity, 70)
  
  async def _test_codec_format_audio_io_container(self, codec: AudioCodecInfo, format: str, transcode: bool):
    output_container = OutputContainer(self.container_filename, format=format)
    in_samples = await self.out_container_write_audio(output_container.add_audio_stream(codec), codec)
    await output_container.close()
    
    input_container = InputContainer(self.container_filename, format=format)
    out_samples = await self.in_container_read_audio(input_container.get_audio_stream(0, transcode), codec, transcode)
    await input_container.close()
    
    similarity = get_freq_similarity(get_spectum(in_samples), get_spectum(out_samples)) # lower is better
    self.assertLess(similarity, 70)
  
  async def _test_codec_format_video_io_container(self, codec: VideoCodecInfo, format: str, transcode: bool):
    output_container = OutputContainer(self.container_filename, format=format)
    in_frames = await self.out_container_write_video(output_container.add_video_stream(codec), codec)
    await output_container.close()
    
    input_container = InputContainer(self.container_filename, format=format)
    out_frames = await self.in_container_read_video(input_container.get_video_stream(0, transcode), codec, transcode)

    print("Decoded frames: {}".format(len(out_frames)))
    self.assertGreater(len(out_frames), 0)
    for a, b in zip(out_frames, in_frames):
      self.assertLess(np.abs(a-b).sum(), frame_box_size_value * 0.01) # allow for 1% error
      
    await input_container.close()
  
  async def out_container_write_audio(self, audio_stream: AVOutputStream, codec: AudioCodecInfo):
    encoder = codec.get_encoder()
    in_samples = create_audio_track(10, codec.sample_rate)
    resampler = codec.get_resampler()
    complete_frame = AudioFrame.from_ndarray(in_samples[np.newaxis,:], "s16", 1, codec.sample_rate)
    frames = await resampler.resample(complete_frame)
    
    try:
      for frame in frames:
        for packet in await encoder.encode(frame):
          await audio_stream.mux(packet)
    
      for packet in await encoder.flush():
        await audio_stream.mux(packet)
    except asyncio.CancelledError: pass
        
    encoder.close()
    return in_samples
  
  async def in_container_read_audio(self, audio_stream: AVInputStream, codec: AudioCodecInfo, transcode: bool) -> np.ndarray:
    if transcode:
      in_codec = audio_stream.codec_info
      self.assertTrue(codec.compatible_with(in_codec))
   
    decoder = codec.get_decoder() # Decoder(in_audio_stream._stream.codec_context, codec.time_base)
    out_samples = []

    validation_codec = AudioCodecInfo("pcm_s16le", codec.channels, codec.sample_rate, "s16")
    validation_resampler = validation_codec.get_resampler()
  
    with self.assertRaises(EOFError):
      while True:
        for packet in await audio_stream.demux():
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

    return np.concatenate(out_samples, axis=1)[0]
  
  async def out_container_write_video(self, video_stream: AVOutputStream, codec: VideoCodecInfo):
    encoder = codec.get_encoder()
    in_frames = list(generate_frames(codec.width, codec.height, int(10 * codec.frame_rate)))
    try:
      for frame in in_frames:
        for packet in await encoder.encode(VideoFrame.from_ndarray(frame, "rgb24").convert(pixel_format=codec.pixel_format)):
          await video_stream.mux(packet)
          
      for packet in await encoder.flush():
        await video_stream.mux(packet)
    except asyncio.CancelledError: pass
        
    encoder.close()
    return in_frames
  
  async def in_container_read_video(self, video_stream: AVInputStream, codec: VideoCodecInfo, transcode: bool):
    if transcode:
      in_codec = video_stream.codec_info
      self.assertTrue(codec.compatible_with(in_codec))
   
    decoder = codec.get_decoder()
    out_frames: np.ndarray = []

    with self.assertRaises(EOFError):
      while True:
        packets = await video_stream.demux()
        for packet in packets:
          for frame in await decoder.decode(packet):
            out_frames.append(normalize_video_frame(frame))

    flushed_frames = 0 # flushed frames may be scuffed
    try:
      for frame in await decoder.flush():
        flushed_frames += 1
        out_frames.append(normalize_video_frame(frame))
    except EOFError: pass
    
    if flushed_frames == 0: return out_frames
    return out_frames[:-flushed_frames]

if __name__ == '__main__':
  unittest.main()
