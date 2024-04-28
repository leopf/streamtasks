import asyncio
import os
import tempfile
import unittest
from streamtasks.media.audio import AudioCodecInfo
from streamtasks.media.container import AVInputStream, AVOutputStream, InputContainer, OutputContainer
from streamtasks.media.video import VideoCodecInfo
from tests.media import decode_audio_packets, decode_video_packets, demux_all_packets, encode_all_frames, frame_box_size_value, generate_audio_media_track, generate_media_frames, get_freq_similarity, get_spectrum, mux_all_packets
import numpy as np
from tests.shared import full_test

@full_test
class TestContainers(unittest.IsolatedAsyncioTestCase):
  def setUp(self) -> None:
    self.container_filename = tempfile.mktemp()
    self.duration = 4
  
  def tearDown(self) -> None:
    os.remove(self.container_filename)
  async def test_mp4_av_container_basic(self): await self._test_mp4_av_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "mpeg4"), AudioCodecInfo("aac", 2, 32000, "fltp"))
  @unittest.skip("h264 broken")
  async def test_mp4_h264_video_container(self): await self._test_codec_format_video_io_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "h264"), "mp4", True)
  @unittest.skip("hevc missing")
  async def test_mp4_h265_video_container(self): await self._test_codec_format_video_io_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "libx265"), "mp4", True, skip_end=2)
  async def test_webm_video_container(self): await self._test_codec_format_video_io_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "vp8"), "webm", False, skip_start=2)
  async def test_mp4_1_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("aac", 2, 32000, "fltp"), "mp4", False)
  async def test_mp4_2_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("aac", 1, 16000, "fltp"), "mp4", False)
  async def test_wav_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("pcm_s16le", 1, 16000, "s16"), "wav", False)
  async def test_flac_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("flac", 1, 16000, "s16"), "flac", False)
  
  async def _test_mp4_av_container(self, video_codec: VideoCodecInfo, audio_codec: AudioCodecInfo):
    output_container = await OutputContainer.open(self.container_filename, format="mp4")
    in_audio_frames, in_samples = await generate_audio_media_track(audio_codec, self.duration)
    in_video_frames, in_frames = generate_media_frames(video_codec, self.duration * video_codec.frame_rate)
    in_audio_packets = await encode_all_frames(audio_codec.get_encoder(), in_audio_frames)
    in_video_packets = await encode_all_frames(video_codec.get_encoder(), in_video_frames)
    
    _, pending = await asyncio.wait((
      asyncio.create_task(mux_all_packets(output_container.add_video_stream(video_codec), in_video_packets)),
      asyncio.create_task(mux_all_packets(output_container.add_audio_stream(audio_codec), in_audio_packets)),
    ), return_when="FIRST_COMPLETED")
    
    for p in pending: p.cancel()
    await output_container.close()
    
    input_container = await InputContainer.open(self.container_filename, format="mp4")
    audio_stream = input_container.get_audio_stream(0, audio_codec)
    video_stream = input_container.get_video_stream(0, video_codec, True)
    
    out_tasks = (
      asyncio.create_task(demux_all_packets(audio_stream)),
      asyncio.create_task(demux_all_packets(video_stream))
    )
    _, pending = await asyncio.wait(out_tasks, return_when="ALL_COMPLETED")
    for p in pending: p.cancel()
    out_audio_packets, out_video_packets = await out_tasks[0], await out_tasks[1]
    await input_container.close()
    
    out_frames = await decode_video_packets(video_codec, out_video_packets)
    out_samples = await decode_audio_packets(audio_codec, out_audio_packets)
    
    self.check_video_error(in_frames, out_frames, skip_end=3)
    self.check_audio_error(in_samples, out_samples, audio_codec.rate)
  
  async def _test_codec_format_audio_io_container(self, codec: AudioCodecInfo, format: str, force_transcode: bool):
    output_container = await OutputContainer.open(self.container_filename, format=format)
    in_samples = await self.out_container_write_audio(output_container.add_audio_stream(codec), codec)
    await output_container.close()
    
    input_container = await InputContainer.open(self.container_filename, format=format)
    out_samples = await self.in_container_read_audio(input_container.get_audio_stream(0, codec, force_transcode), codec, force_transcode)
    await input_container.close()
    
    self.check_audio_error(in_samples, out_samples, codec.rate)
  
  async def _test_codec_format_video_io_container(self, codec: VideoCodecInfo, format: str, force_transcode: bool, skip_start=0, skip_end=0):
    output_container = await OutputContainer.open(self.container_filename, format=format)
    in_frames = await self.out_container_write_video(output_container.add_video_stream(codec), codec)
    await output_container.close()
    
    input_container = await InputContainer.open(self.container_filename, format=format)
    out_frames = await self.in_container_read_video(input_container.get_video_stream(0, codec, force_transcode), codec, force_transcode)
    await input_container.close()
    
    self.check_video_error(in_frames, out_frames, skip_start=skip_start, skip_end=skip_end)
      
  async def out_container_write_audio(self, stream: AVOutputStream, codec: AudioCodecInfo):
    frames, samples = await generate_audio_media_track(codec, self.duration)
    await mux_all_packets(stream, await encode_all_frames(codec.get_encoder(), frames))
    return samples
  
  async def in_container_read_audio(self, stream: AVInputStream, codec: AudioCodecInfo, transcode: bool) -> np.ndarray:
    if transcode: self.assertTrue(codec.compatible_with(stream.codec_info))
    packets = list(await demux_all_packets(stream))
    return await decode_audio_packets(codec, packets)
  
  async def out_container_write_video(self, stream: AVOutputStream, codec: VideoCodecInfo):
    frames, frames_raw = generate_media_frames(codec, self.duration * codec.frame_rate)
    await mux_all_packets(stream, await encode_all_frames(codec.get_encoder(), frames))
    return frames_raw
  
  async def in_container_read_video(self, stream: AVInputStream, codec: VideoCodecInfo, transcode: bool):
    if transcode: self.assertTrue(codec.compatible_with(stream.codec_info))
    return await decode_video_packets(codec, list(await demux_all_packets(stream)))

  def check_video_error(self, in_frames: list[np.ndarray], out_frames: list[np.ndarray], skip_start: int = 0, skip_end: int = 0):
    frame_count = min(len(in_frames), len(out_frames))
    in_frames = in_frames[skip_start:len(in_frames) - skip_end]
    out_frames = out_frames[skip_start:len(out_frames) - skip_end]
    self.assertGreater(len(out_frames), 0)
    self.assertGreater(len(in_frames), 0)
    for index, (a, b) in enumerate(zip(out_frames, in_frames)):
      self.assertLess(np.abs(a-b).sum(), frame_box_size_value * 0.01, f"failed at frame {index + skip_start}/{frame_count}") # allow for 1% error
      
  def check_audio_error(self, in_samples: list[np.ndarray], out_samples: list[np.ndarray], rate: int):
    audio_similarity = get_freq_similarity(get_spectrum(in_samples, sample_rate=rate), get_spectrum(out_samples, sample_rate=rate)) # lower is better
    self.assertLess(audio_similarity, 70) # TODO: this is too high

if __name__ == '__main__':
  unittest.main()
