import numpy as np

from streamtasks.media.video import VideoFrame

def create_audio_samples(sample_rate: int,  freq: int, duration: float) -> bytes:
  return np.sin(2 * np.pi * np.arange(int(sample_rate * duration)) * freq / sample_rate)

def create_audio_track(duration: float, sample_rate: int, ):
    samples = create_audio_samples(sample_rate, 420, duration) + create_audio_samples(sample_rate, 69, duration) + create_audio_samples(sample_rate, 111, duration)
    return (samples * 10000).astype(np.int16)
  
def generate_frames(w, h, frame_count):
  for i in range(frame_count):
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    # draw 40x40 square at (i, i)
    y = i % (h - 40)
    x = i % (w - 40)
    arr[y:y + 40, x:x + 40] = 255
    yield arr
  
def normalize_video_frame(frame: VideoFrame):
  np_frame = frame.to_rgb().to_ndarray()
  # remove alpha channel from argb
  np_frame = np_frame[:, :, :3]
  # round frame to 0 or 255
  np_frame = np.where(np_frame > 127, 255, 0)
  return np_frame