import asyncio
import os
import tempfile
import unittest
from streamtasks.media.audio import AudioCodecInfo, AudioFrame
from streamtasks.media.container import AVInputStream, AVOutputStream, InputContainer, OutputContainer
from streamtasks.media.video import VideoCodecInfo, VideoFrame
from tests.media import decode_all_packets, demux_all_packets, encode_all_frames, frame_box_size_value, generate_audio_media_track, generate_media_frames, get_freq_similarity, get_spectum, normalize_video_frame
import numpy as np
from tests.shared import full_test


class TestContainers(unittest.IsolatedAsyncioTestCase):
  async def asyncSetUp(self) -> None:
    self.container_filename = tempfile.mktemp()
    self.duration = 6
  
  async def asyncTearDown(self) -> None:
    os.remove(self.container_filename)
  
  async def test_mp4_h264_video_container(self): await self._test_codec_format_video_io_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "h264"), "mp4", True)
  # @unittest.skip("Looks fine, but high error")
  @full_test
  async def test_mp4_h265_video_container(self): await self._test_codec_format_video_io_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "hevc"), "mp4", True, (1, 2))
  @full_test
  async def test_webm_video_container(self): await self._test_codec_format_video_io_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "vp8"), "webm", False, (3, 3))
  async def test_mp4_1_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("aac", 2, 32000, "fltp"), "mp4", False)
  @unittest.skip("flaky, need to fix this...")
  @full_test
  async def test_mp4_2_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("aac", 1, 16000, "fltp"), "mp4", False)
  @full_test
  async def test_wav_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("pcm_s16le", 1, 16000, "s16"), "wav", False)
  @full_test
  async def test_flac_audio_container(self): await self._test_codec_format_audio_io_container(AudioCodecInfo("flac", 1, 16000, "s16"), "flac", False)
  @unittest.skip("flaky")
  async def test_mp4_av_container_basic(self): await self._test_mp4_av_container(VideoCodecInfo(1280, 720, 30, "yuv420p", "h264"), AudioCodecInfo("aac", 2, 32000, "fltp"))
  
  async def _test_mp4_av_container(self, video_codec: VideoCodecInfo, audio_codec: AudioCodecInfo):
    output_container = await OutputContainer.open(self.container_filename, format="mp4")
    in_tasks = (
      asyncio.create_task(self.out_container_write_audio(output_container.add_audio_stream(audio_codec), audio_codec)),
      asyncio.create_task(self.out_container_write_video(output_container.add_video_stream(video_codec), video_codec))
    )
    _, pending = await asyncio.wait(in_tasks, return_when="FIRST_COMPLETED")
    for p in pending: p.cancel()
    in_samples, in_frames = await in_tasks[0], await in_tasks[1]
    await output_container.close()
    
    input_container = await InputContainer.open(self.container_filename, format="mp4")
    audio_stream = input_container.get_audio_stream(0, audio_codec)
    video_stream = input_container.get_video_stream(0, video_codec, True)
    
    out_tasks = (
      asyncio.create_task(self.in_container_read_audio(audio_stream, audio_codec, False)),
      asyncio.create_task(self.in_container_read_video(video_stream, video_codec, True))
    )
    await asyncio.sleep(0.5) # HACK this is shit, need to fix
    _, pending = await asyncio.wait(out_tasks, return_when="FIRST_COMPLETED")
    for p in pending: p.cancel()
    out_samples, out_frames = await out_tasks[0], await out_tasks[1]
    await input_container.close()
    
    self.assertGreater(len(out_frames), 0)
    self.assertGreater(len(in_frames), 0)
    for a, b in zip(out_frames, in_frames):
      self.assertLess(np.abs(a-b).sum(), frame_box_size_value * 0.01) # allow for 1% error

    audio_similarity = get_freq_similarity(get_spectum(in_samples), get_spectum(out_samples)) # lower is better
    self.assertLess(audio_similarity, 150)
  
  async def _test_codec_format_audio_io_container(self, codec: AudioCodecInfo, format: str, force_transcode: bool):
    output_container = await OutputContainer.open(self.container_filename, format=format)
    in_samples = await self.out_container_write_audio(output_container.add_audio_stream(codec), codec)
    await output_container.close()
    
    input_container = await InputContainer.open(self.container_filename, format=format)
    out_samples = await self.in_container_read_audio(input_container.get_audio_stream(0, codec, force_transcode), codec, force_transcode)
    await input_container.close()
    
    similarity = get_freq_similarity(get_spectum(in_samples), get_spectum(out_samples)) # lower is better
    self.assertLess(similarity, 70)
  
  async def _test_codec_format_video_io_container(self, codec: VideoCodecInfo, format: str, force_transcode: bool, check_padding: tuple[int,int] = (0, 0)):
    output_container = await OutputContainer.open(self.container_filename, format=format)
    in_frames = await self.out_container_write_video(output_container.add_video_stream(codec), codec)
    await output_container.close()
    
    input_container = await InputContainer.open(self.container_filename, format=format)
    out_frames = await self.in_container_read_video(input_container.get_video_stream(0, codec, force_transcode), codec, force_transcode)

    in_frames = in_frames[check_padding[0]:len(in_frames) - check_padding[1]]
    out_frames = out_frames[check_padding[0]:len(out_frames) - check_padding[1]]

    self.assertGreater(len(out_frames), 0)
    self.assertGreater(len(in_frames), 0)
    for a, b in zip(out_frames, in_frames):
      self.assertLess(np.abs(a-b).sum(), frame_box_size_value * 0.01) # allow for 1% error
      
    await input_container.close()
  
  async def out_container_write_audio(self, audio_stream: AVOutputStream, codec: AudioCodecInfo):
    frames, in_samples = await generate_audio_media_track(codec, self.duration)
    packets = await encode_all_frames(codec.get_encoder(), frames)
    try:
      for packet in packets: await audio_stream.mux(packet)
    except asyncio.CancelledError: pass    
    return in_samples
  
  async def in_container_read_audio(self, stream: AVInputStream, codec: AudioCodecInfo, transcode: bool) -> np.ndarray:
    if transcode: self.assertTrue(codec.compatible_with(stream.codec_info))
    validation_codec = AudioCodecInfo("pcm_s16le", codec.channels, codec.sample_rate, "s16")
    validation_resampler = validation_codec.get_resampler()
    packets = list(await demux_all_packets(stream))
    out_frames: list[AudioFrame] = []
    for frame in await decode_all_packets(codec.get_decoder(), packets): out_frames.extend(await validation_resampler.resample(frame))
    out_frames: list[np.ndarray] = [ frame.to_ndarray() for frame in out_frames ]

    return np.concatenate(out_frames, axis=1)[0]
  
  async def out_container_write_video(self, video_stream: AVOutputStream, codec: VideoCodecInfo):
    in_frames, in_frames_raw = generate_media_frames(codec, self.duration * codec.frame_rate)
    packets = await encode_all_frames(codec.get_encoder(), in_frames)
    try:
      for packet in packets: await video_stream.mux(packet)
    except asyncio.CancelledError: pass
    return in_frames_raw
  
  async def in_container_read_video(self, stream: AVInputStream, codec: VideoCodecInfo, transcode: bool):
    if transcode: self.assertTrue(codec.compatible_with(stream.codec_info))
    packets = list(await demux_all_packets(stream))
    out_frames: list[VideoFrame] = await decode_all_packets(codec.get_decoder(), packets)
    out_frames: list[np.ndarray] = [ normalize_video_frame(f) for f in out_frames ]
    return out_frames

if __name__ == '__main__':
  unittest.main()
