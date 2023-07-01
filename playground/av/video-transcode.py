from streamtasks.media.video import VideoCodecInfo, VideoFrame
from streamtasks.message import MediaPacket
import numpy as np
import matplotlib.pyplot as plt
import asyncio
import cv2
import time
w, h = 480, 360

async def display_frame(name: str, f: np.ndarray):
    e = asyncio.Event()
    def show():
        cv2.imshow(name, f.astype(dtype=np.uint8))
        cv2.waitKey(1)
        e.set()
    asyncio.get_running_loop().call_soon_threadsafe(show)
    await e.wait()
    # await asyncio.sleep(0.02)


def generate_frames(frame_count):
    for i in range(frame_count):
        arr = np.zeros((h, w, 3), dtype=np.uint8)
        # draw 40x40 square at (i, i)
        y = i % (h - 40)
        x = i % (w - 40)
        arr[y:y+40, x:x+40] = 255
        yield arr

def get_video_codec(crf, codec='h264', pixel_format='yuv420p'):
    return VideoCodecInfo(w, h, 1, crf=crf, codec=codec, pixel_format=pixel_format)

def normalize_video_frame(frame: VideoFrame):
    np_frame = frame.to_rgb().to_ndarray()
    # remove alpha channel from argb
    np_frame = np_frame[:, :, :3]
    # round frame to 0 or 255
    np_frame = np.where(np_frame > 127, 255, 0)
    return np_frame


async def main():
    frame_count = 500
    codec1 = get_video_codec(crf=0)
    codec2 = get_video_codec(crf=0, codec='libvpx-vp9', pixel_format='yuv420p')
    transcoder = codec1.get_transcoder(codec2)
    encoder = codec1.get_encoder()
    decoder = codec2.get_decoder()

    created_frames = []
    for frame in generate_frames(frame_count):
        created_frames.append(frame)
        e_packets: list[MediaPacket] = await encoder.encode(VideoFrame.from_ndarray(frame, 'rgb24'))
        for e_p in e_packets:
            t_packets: list[MediaPacket] = await transcoder.transcode(e_p)
            for t_p in t_packets:
                decoded: list[VideoFrame] = await decoder.decode(t_p)
                for d in decoded:
                    decoded_frame = normalize_video_frame(d)
                    expected_frame = created_frames.pop(0)

                    # plt.subplot(1, 2, 1)
                    await display_frame("input", expected_frame)
                    # plt.subplot(1, 2, 2)
                    await display_frame("output", decoded_frame)
                    # plt.show()
            # self.assertTrue(np.array_equal(decoded_frame, frame))

if __name__ == '__main__':
    asyncio.run(main())
    cv2.destroyAllWindows()