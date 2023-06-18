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

def get_spectum(samples: np.ndarray):
    freqs = scipy.fft.fft(samples)
    freqs = freqs[range(int(len(freqs)/2))] # keep only first half
    freqs = abs(freqs) # get magnitude
    freqs = freqs / freqs.sum() # normalize
    return freqs

def reduce_freqs(samples: np.ndarray, reduce: int):
    if samples.shape[0] % reduce != 0:
        samples = samples[:-(samples.shape[0] % reduce)]

    res = samples.reshape(-1, reduce)
    res = res.sum(axis=-1)
    return res

def get_freq_similarity(a: np.ndarray, b: np.ndarray, n_freqs: int):
    a_freqs = np.argsort(a)[-n_freqs:]
    b_freqs = np.argsort(b)[-n_freqs:]
    a_freqs.sort()
    b_freqs.sort()

    print("a_freqs: ", a_freqs)
    print("b_freqs: ", b_freqs)

    return np.abs(a_freqs-b_freqs).sum()

def analyse_samples(in_samples: np.ndarray, out_samples: np.ndarray):
    freq_size = 1000
    freq_reduce = 10
    in_spectrum = get_spectum(in_samples)[:freq_size]
    out_spectrum = get_spectum(out_samples)[:freq_size]

    a = reduce_freqs(out_spectrum, freq_reduce)
    diff_spectrum = reduce_freqs(in_spectrum, freq_reduce) - reduce_freqs(out_spectrum, freq_reduce)
    print("diff_spectrum sum: ", diff_spectrum.sum())

    print("similarity: ", get_freq_similarity(in_spectrum, out_spectrum, 2))

    f, (p1, p2, p3) = plt.subplots(3, 1)
    p1.plot(diff_spectrum)
    p2.plot(in_spectrum)
    p3.plot(out_spectrum)
    plt.show()

async def main1():
    duration = 1
    samples = create_samples(420, duration) + create_samples(69, duration) + create_samples(75, duration)
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
    analyse_samples(samples, audio_parts[0])

async def main2():
    duration = 3
    samples = create_samples(420, duration) + create_samples(69, duration) + create_samples(75, duration)
    samples = (samples * 10000).astype(np.int16)

    codec_info1 = AudioCodecInfo("aac", 1, sample_rate, "fltp", bitrate=10000)
    codec_info2 = AudioCodecInfo("ac3", 1, sample_rate, "fltp", bitrate=1000000)
    transcoder = codec_info1.get_transcoder(codec_info2)
    encoder = codec_info1.get_encoder()
    decoder = codec_info2.get_decoder()

    resampler = AudioCodecInfo("pcm_s16le", 1, sample_rate, "s16").get_resampler()
    
    frame = AudioFrame.from_ndarray(samples[np.newaxis, :], "s16", 1, sample_rate)
    audio_parts = []
    for packet in await encoder.encode(frame):
        t_packets = await transcoder.transcode(packet)
        for t_packet in t_packets:
            new_frames = await decoder.decode(t_packet)
            for new_frame in new_frames:
                for r_frame in await resampler.resample(new_frame):
                    audio_parts.append(r_frame.to_ndarray())

    # merge audio parts
    audio_parts = np.concatenate(audio_parts, axis=1)
    play_samples(audio_parts[0])
    analyse_samples(samples, audio_parts[0])


if __name__ == '__main__':
    asyncio.run(main2())