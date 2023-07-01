import unittest
from streamtasks.media.audio import AudioCodecInfo, AudioFrame
from streamtasks.media.types import MediaPacket
import numpy as np
import scipy

class TestAudioCodec(unittest.IsolatedAsyncioTestCase):
  sample_rate = 44100
  freq_count = 3

  def setUp(self):
    self.resampler = self.get_audio_codec("pcm_s16le", "s16").get_resampler()

  def create_samples(self, freq: int, duration: float) -> bytes:
    return np.sin(2 * np.pi * np.arange(int(self.sample_rate * duration)) * freq / self.sample_rate)

  def create_track(self, duration: float = 1):
    samples = self.create_samples(420, duration) + self.create_samples(69, duration) + self.create_samples(111, duration)
    return (samples * 10000).astype(np.int16)

  def get_audio_codec(self, codec: str, pixel_format: str):
    return AudioCodecInfo(
      codec=codec,
      channels=1,
      sample_rate=self.sample_rate,
      sample_format=pixel_format,
    )
  
  def resample_audio_frame(self, frame: AudioFrame):
    return self.resampler.resample(frame)

  def get_spectum(self, samples: np.ndarray):
    freqs = scipy.fft.fft(samples)
    freqs = freqs[range(int(len(freqs)/2))] # keep only first half
    freqs = abs(freqs) # get magnitude
    freqs = freqs / freqs.sum() # normalize
    return freqs

  def get_freq_similarity(self, a: np.ndarray, b: np.ndarray):
    a_freqs = np.argsort(a)[-self.freq_count:]
    b_freqs = np.argsort(b)[-self.freq_count:]
    a_freqs.sort()
    b_freqs.sort()
    return np.abs(a_freqs-b_freqs).sum()

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

    in_freqs = self.get_spectum(in_samples)
    out_freqs = self.get_spectum(out_samples)
    similarity = self.get_freq_similarity(in_freqs, out_freqs) # lower is better
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

    in_freqs = self.get_spectum(in_samples)
    out_freqs = self.get_spectum(out_samples)
    similarity = self.get_freq_similarity(in_freqs, out_freqs)
    self.assertLess(similarity, 40)

if __name__ == '__main__':
  unittest.main()
