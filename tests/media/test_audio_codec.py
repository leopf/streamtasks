import unittest
from streamtasks.media.audio import AudioCodecInfo, AudioFrame
import numpy as np

from tests.media import generate_audio_track, get_freq_similarity, get_spectum

class TestAudioCodec(unittest.IsolatedAsyncioTestCase):
  sample_rate = 44100
  freq_count = 3

  def setUp(self):
    self.resampler = self.get_audio_codec("pcm_s16le", "s16").get_resampler()

  def create_track(self, duration: float = 1): return generate_audio_track(duration, self.sample_rate)

  def get_audio_codec(self, codec: str, sample_format: str):
    return AudioCodecInfo(
      codec=codec,
      channels=1,
      sample_rate=self.sample_rate,
      sample_format=sample_format,
    )

  def resample_audio_frame(self, frame: AudioFrame):
    return self.resampler.resample(frame)

  async def test_inverse_transcoder(self):
    in_samples = self.create_track()
    codec_info = self.get_audio_codec("aac", "fltp")
    encoder = codec_info.get_encoder()
    decoder = codec_info.get_decoder()

    frame = AudioFrame.from_ndarray(in_samples[np.newaxis, :], "s16", 1, self.sample_rate)
    encoded_packets = await encoder.encode(frame)
    out_samples = []
    for packet in encoded_packets:
      new_frames = await decoder.decode(packet)
      for new_frame in new_frames:
        for r_frame in await self.resample_audio_frame(new_frame):
          out_samples.append(r_frame.to_ndarray())

    out_samples = np.concatenate(out_samples, axis=1)[0]

    similarity = get_freq_similarity(get_spectum(in_samples), get_spectum(out_samples)) # lower is better
    self.assertLess(similarity, 20)

  async def test_transcoder(self):
    in_samples = self.create_track(5)
    codec_info1 = self.get_audio_codec("aac", "fltp")
    codec_info2 = self.get_audio_codec("ac3", "fltp")
    transcoder = codec_info1.get_transcoder(codec_info2)
    encoder = codec_info1.get_encoder()
    decoder = codec_info2.get_decoder()

    frame = AudioFrame.from_ndarray(in_samples[np.newaxis, :], "s16", 1, self.sample_rate)
    out_samples = []
    for packet in await encoder.encode(frame):
      t_packets = await transcoder.transcode(packet)
      for t_packet in t_packets:
        for r_frame in await decoder.decode(t_packet):
          for rs_frame in await self.resample_audio_frame(r_frame):
            out_samples.append(rs_frame.to_ndarray())

    out_samples = np.concatenate(out_samples, axis=1)[0]

    similarity = get_freq_similarity(get_spectum(in_samples), get_spectum(out_samples)) # lower is better
    self.assertLess(similarity, 40)


if __name__ == '__main__':
  unittest.main()
