import asyncio
from typing import Iterable
import numpy as np
import scipy.fft

from streamtasks.media.audio import AudioCodecInfo, AudioFrame
from streamtasks.media.codec import Decoder, Encoder
from streamtasks.media.container import AVInputStream, AVOutputStream
from streamtasks.media.packet import MediaPacket
from streamtasks.media.video import VideoCodecInfo, VideoFrame

async def encode_all_frames(encoder: Encoder, frames: list):
  packets: list[MediaPacket] = []
  for frame in frames: packets.extend(await encoder.encode(frame))
  packets.extend(await encoder.flush())
  return packets 

async def decode_all_packets(decoder: Decoder, packets: Iterable[MediaPacket]):
  frames = []
  for packet in packets: frames.extend(await decoder.decode(packet))
  frames.extend(await decoder.flush())
  return frames

async def demux_all_packets(stream: AVInputStream):
  packets: list[MediaPacket] = []
  try:
    while True: 
      for packet in await stream.demux():
        packets.append(packet)
  except EOFError: pass
  return packets

async def decode_video_packets(codec: VideoCodecInfo, packets: list[MediaPacket]):
  out_frames: list[VideoFrame] = await decode_all_packets(codec.get_decoder(), packets)
  out_frames: list[np.ndarray] = [ normalize_video_frame(f) for f in out_frames ]
  return out_frames

def audio_frames_to_samples(frames: list[AudioFrame]): return np.concatenate([ frame.to_ndarray() for frame in frames ], axis=1)[0]
async def audio_frames_to_s16_samples(frames: list[AudioFrame], codec: AudioCodecInfo):
  validation_codec = AudioCodecInfo("pcm_s16le", codec.channels, codec.sample_rate, "s16")
  validation_resampler = validation_codec.get_resampler()
  out_frames: list[AudioFrame] = []
  for frame in frames: out_frames.extend(await validation_resampler.resample_one(frame))
  return audio_frames_to_samples(out_frames)

async def decode_audio_packets(codec: AudioCodecInfo, packets: list[MediaPacket]) -> np.ndarray:
  return await audio_frames_to_s16_samples(await decode_all_packets(codec.get_decoder(), packets), codec)

async def mux_all_packets(stream: AVOutputStream, packets: Iterable[MediaPacket]):
  try:
    for packet in packets: await stream.mux(packet)
  except asyncio.CancelledError: pass

def generate_audio_samples(sample_rate: int,  freq: int, duration: float) -> bytes:
  return np.sin(2 * np.pi * np.arange(int(sample_rate * duration)) * freq / sample_rate)

_audio_track_freq_count = 3

def generate_audio_track(duration: float, sample_rate: int) -> np.ndarray:
    samples = generate_audio_samples(sample_rate, 420, duration) + generate_audio_samples(sample_rate, 69, duration) + generate_audio_samples(sample_rate, 111, duration)
    return (samples * 10000).astype(np.int16)

async def generate_audio_media_track(codec: AudioCodecInfo, duration: float):
  audio_samples = generate_audio_track(duration, codec.sample_rate * codec.channels)
  audio_resampler = codec.get_resampler()
  audio_frame = AudioFrame.from_ndarray(audio_samples[np.newaxis,:], "s16", codec.channels, codec.sample_rate)
  return await audio_resampler.resample_one(audio_frame), audio_samples

frame_box_size = (40, 40)
frame_box_size_value = frame_box_size[0] * frame_box_size[1] * 255
def generate_frames(w, h, frame_count):
  speed = int(max(min(w, h) / frame_count, 1))
  for i in range(frame_count):
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    # draw 40x40 square at (i, i)
    y = (i * speed) % (h - frame_box_size[1])
    x = (i * speed) % (w - frame_box_size[0])
    arr[y:y + frame_box_size[1], x:x + frame_box_size[0]] = 255
    yield arr
  
def generate_media_frames(codec: VideoCodecInfo, frame_count: int):
  raw_frames = list(generate_frames(codec.width, codec.height, frame_count))
  frames: list[VideoFrame] = []
  for frame in raw_frames:
    frames.append(VideoFrame.from_ndarray(frame, "rgb24").convert(pixel_format=codec.pixel_format))
  return frames, raw_frames
  
def normalize_video_frame(frame: VideoFrame):
  np_frame = frame.to_rgb().to_ndarray()
  # remove alpha channel from argb
  np_frame = np_frame[:, :, :3]
  # round frame to 0 or 255
  np_frame = np.where(np_frame > 127, 255, 0)
  return np_frame

def get_spectrum(samples: np.ndarray, sample_rate: int | None = None):
  sample_rate = sample_rate or samples.size
  raw_spec = scipy.fft.rfft(samples)
  raw_spec = abs(raw_spec)
  spec = np.zeros((sample_rate // 2))
  sum_size = raw_spec.size / spec.size
  sum_index = 0
  for i in range(spec.size):
      spec[i] = raw_spec[int(sum_index):int(sum_index + sum_size)].sum()
      sum_index += sum_size
  spec = spec / spec.sum()
  return spec

# TODO maybe tweak this a little to make it more reliable
def get_freq_peeks(spec: np.ndarray, conv_count = 5):
    conv_kernel = np.ones((11))
    conv_kernel[5] = 2
    conv_kernel = conv_kernel / conv_kernel.sum()
    for _ in range(conv_count):
        spec = np.convolve(spec, conv_kernel, mode="same")
    spec[spec < spec.max() / 4] = 0
    spec = spec[:-1] > spec[1:]
    spec = spec[:-1] > spec[1:]
    return np.where(spec > 0)[0]

def get_freq_similarity(a: np.ndarray, b: np.ndarray):
  a_freqs = get_freq_peeks(a)
  b_freqs = get_freq_peeks(b)
  a_freqs.sort()
  b_freqs.sort()
  size = min(a_freqs.size, b_freqs.size)
  assert size > 0, "no frequency peeks found"
  a_freqs = a_freqs[:size]
  b_freqs = b_freqs[:size]
  
  return np.abs(a_freqs - b_freqs).sum()