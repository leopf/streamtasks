import scipy
import numpy as np
import simpleaudio as sa
from matplotlib import pyplot as plt
import asyncio
from streamtasks.media.audio import AudioCodecInfo, AudioFrame

sample_rate = 44100

def create_samples(freq: int, duration: float) -> bytes:
    return np.sin(2 * np.pi * np.arange(int(sample_rate * duration)) * freq / sample_rate)

def play_samples(samples: np.ndarray):
    play = sa.play_buffer(samples, 1, 2, sample_rate)
    play.wait_done()

def display_spectrum(samples: np.ndarray, until: int = 1000):
    # get frequency spectrum 
    freqs = scipy.fft.fft(samples)
    freqs = freqs[range(int(len(freqs)/2))] # keep only first half
    freqs = abs(freqs) # get magnitude
    freqs = freqs / np.max(freqs) # normalize

    # display frequency spectrum
    plt.plot(freqs[:until]) 

async def main():
    samples = create_samples(420, 1) + create_samples(69, 1)
    samples = (samples * 10000).astype(np.int16)

    codec_info = AudioCodecInfo("aac", 1, sample_rate, "fltp", bitrate=10000)
    encoder = codec_info.get_encoder()
    print("frame_size: ", encoder.codec_context.frame_size)
    decoder = codec_info.get_decoder()

    resampler_info = AudioCodecInfo("pcm_s16le", 1, sample_rate, "s16")
    resampler = resampler_info.get_resampler()
    
    frame = AudioFrame.from_ndarray(samples[np.newaxis, :], "s16", 1, sample_rate)
    encoded_packets = await encoder.encode(frame)
    audio_parts = []
    for packet in encoded_packets:
        new_frames = await decoder.decode(packet)
        for new_frame in new_frames:
            for r_frame in await resampler.resample(new_frame):
                audio_parts.append(r_frame.to_ndarray())

    # merge audio parts
    audio_parts = np.concatenate(audio_parts, axis=1)

    loop = asyncio.get_running_loop()
    loop.call_soon_threadsafe(play_samples, audio_parts[0])
    loop.call_soon_threadsafe(play_samples, samples)

    display_spectrum(samples)
    display_spectrum(audio_parts[0])
    plt.show()

if __name__ == '__main__':
    asyncio.run(main())