import numpy as np
import scipy

from streamtasks.media.video import VideoFrame

def create_audio_samples(sample_rate: int,  freq: int, duration: float) -> bytes:
  return np.sin(2 * np.pi * np.arange(int(sample_rate * duration)) * freq / sample_rate)

_audio_track_freq_count = 3

def create_audio_track(duration: float, sample_rate: int) -> np.ndarray:
    samples = create_audio_samples(sample_rate, 420, duration) + create_audio_samples(sample_rate, 69, duration) + create_audio_samples(sample_rate, 111, duration)
    return (samples * 10000).astype(np.int16)

frame_box_size = (40, 40)
frame_box_size_value = frame_box_size[0] * frame_box_size[1] * 255
def generate_frames(w, h, frame_count):
  for i in range(frame_count):
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    # draw 40x40 square at (i, i)
    y = i % (h - frame_box_size[1])
    x = i % (w - frame_box_size[0])
    arr[y:y + frame_box_size[1], x:x + frame_box_size[0]] = 255
    yield arr
  

  
def normalize_video_frame(frame: VideoFrame):
  np_frame = frame.to_rgb().to_ndarray()
  # remove alpha channel from argb
  np_frame = np_frame[:, :, :3]
  # round frame to 0 or 255
  np_frame = np.where(np_frame > 127, 255, 0)
  return np_frame

def get_spectum(samples: np.ndarray):
  freqs = scipy.fft.fft(samples)
  freqs = freqs[range(int(len(freqs) / 2))] # keep only first half
  freqs = abs(freqs) # get magnitude
  freqs = freqs / freqs.sum() # normalize
  return freqs

def get_freq_similarity(a: np.ndarray, b: np.ndarray):
  a_freqs = np.argsort(a)[-_audio_track_freq_count:]
  b_freqs = np.argsort(b)[-_audio_track_freq_count:]
  a_freqs.sort()
  b_freqs.sort()
  return np.abs(a_freqs - b_freqs).sum()