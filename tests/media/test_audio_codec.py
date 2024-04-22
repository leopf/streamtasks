import unittest
from streamtasks.media.audio import AudioCodecInfo
from streamtasks.media.packet import MediaPacket
from tests.media import decode_audio_packets, encode_all_frames, generate_audio_media_track, get_freq_similarity, get_spectum

class TestAudioCodec(unittest.IsolatedAsyncioTestCase):
  sample_rate = 44100
  duration = 5

  def get_audio_codec(self, codec: str, sample_format: str):
    return AudioCodecInfo(
      codec=codec,
      channels=1,
      sample_rate=self.sample_rate,
      sample_format=sample_format,
    )

  async def test_inverse_transcoder(self):
    codec = self.get_audio_codec("aac", "fltp")
    frames, in_samples = await generate_audio_media_track(codec, self.duration)
    packets = await encode_all_frames(codec.get_encoder(), frames)
    out_samples = await decode_audio_packets(codec, packets)    
    similarity = get_freq_similarity(get_spectum(in_samples), get_spectum(out_samples)) # lower is better
    self.assertLess(similarity, 25)

  async def test_transcoder(self):
    codec1 = self.get_audio_codec("aac", "fltp")
    codec2 = self.get_audio_codec("ac3", "fltp")
    transcoder = codec1.get_transcoder(codec2)
    frames, in_samples = await generate_audio_media_track(codec1, self.duration)
    encoder1 = codec1.get_encoder()
    packets = await encode_all_frames(encoder1, frames)
    packet_size = encoder1.codec_context.frame_size

    t_packets: list[MediaPacket] = []
    for idx, packet in enumerate(packets): 
      packet.pts = packet_size * idx # add timestamps to packets
      t_packets.extend(await transcoder.transcode(packet))
    t_packets.extend(await transcoder.flush())
    
    self.assertEqual(packets[0].pts, t_packets[0].pts)
    
    out_samples = await decode_audio_packets(codec2, t_packets)    
    similarity = get_freq_similarity(get_spectum(in_samples), get_spectum(out_samples)) # lower is better
    self.assertLess(similarity, 35)

if __name__ == '__main__':
  unittest.main()
