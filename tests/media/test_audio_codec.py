import unittest
from streamtasks.media.audio import AudioCodecInfo
from streamtasks.media.packet import MediaPacket
from tests.media import audio_frames_to_s16_samples, decode_audio_packets, encode_all_frames, generate_audio_media_track, generate_audio_samples, generate_audio_track, get_freq_similarity, get_spectrum

class TestAudioCodec(unittest.IsolatedAsyncioTestCase):
  sample_rates = [44100,32000,16000]
  duration = 5

  async def test_inverse_transcoder(self):
    codec = AudioCodecInfo(codec="aac", channels=1, sample_rate=self.sample_rates[0], sample_format="fltp")
    frames, in_samples = await generate_audio_media_track(codec, self.duration)
    packets = await encode_all_frames(codec.get_encoder(), frames)
    out_samples = await decode_audio_packets(codec, packets)    
    similarity = get_freq_similarity(get_spectrum(in_samples), get_spectrum(out_samples)) # lower is better
    self.assertLess(similarity, 35)

  async def test_transcoder_aac_ac3_1(self):
    codec1 = AudioCodecInfo(codec="aac", channels=1, sample_rate=self.sample_rates[0], sample_format="fltp")
    codec2 = AudioCodecInfo(codec="ac3", channels=1, sample_rate=self.sample_rates[0], sample_format="fltp")
    await self._test_transcoder(codec1, codec2)

  async def test_transcoder_aac_ac3_resample(self):
    codec1 = AudioCodecInfo(codec="aac", channels=1, sample_rate=self.sample_rates[1], sample_format="fltp")
    codec2 = AudioCodecInfo(codec="aac", channels=1, sample_rate=self.sample_rates[2], sample_format="fltp")
    await self._test_transcoder(codec1, codec2)

  async def _test_transcoder(self, codec1: AudioCodecInfo, codec2: AudioCodecInfo):
    transcoder = codec1.get_transcoder(codec2)
    frames, _ = await generate_audio_media_track(codec1, self.duration)
    encoder1 = codec1.get_encoder()
    packets = await encode_all_frames(encoder1, frames)
    packet_size = encoder1.codec_context.frame_size

    t_packets: list[MediaPacket] = []
    for idx, packet in enumerate(packets): 
      packet.pts = packet_size * idx # add timestamps to packets
      t_packets.extend(await transcoder.transcode(packet))
    t_packets.extend(await transcoder.flush())
    
    self.assertEqual(packets[0].pts, t_packets[0].pts)
    self.assertLessEqual(int(t_packets[-1].pts * codec2.time_base), self.duration)
    
    in_samples = await audio_frames_to_s16_samples(frames, codec1)
    out_samples = await decode_audio_packets(codec2, t_packets)
    self.assertLessEqual(out_samples.size - codec2.sample_rate / 2, (codec2.sample_rate / codec1.sample_rate) * in_samples.size, "resampling not working")
    similarity = get_freq_similarity(get_spectrum(in_samples, codec1.sample_rate), get_spectrum(out_samples, codec2.sample_rate)) # lower is better
    self.assertLess(similarity, 35)

if __name__ == '__main__':
  unittest.main()
