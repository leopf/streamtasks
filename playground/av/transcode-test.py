import cv2
import numpy as np
import time 
import asyncio
from matplotlib import pyplot as plt
from streamtasks.media.video import *
from fractions import Fraction
import logging

# setup file log next to this file
logging.basicConfig(filename=__file__ + '.log', level=logging.DEBUG)

w, h = 1920, 1080

def create_img_with_rect(x, y):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[y:y+100, x:x+100] = (255, 255, 255)
    return img


def create_frames():
    for x in range(0, 2000, 5):
        yield create_img_with_rect(x%w, x%h)

async def show_frame(frame):
    plt.imshow(frame)
    plt.show()

async def main():
    for crf in range(0, 51):
        codec_info = VideoCodecInfo(w, h, 30, 'yuv420p', 'h264', 1000000, crf=crf)
        encoder = VideoEncoder(codec_info)
        decoder = VideoDecoder(codec_info)
        data_len = 0

        time_set = int(Fraction(1, 30) / DEFAULT_TIME_BASE)

        for idx, frame in enumerate(create_frames()):
            video_frame = VideoFrame.from_ndarray(frame, 'rgb24')
            packets = await encoder.encode(video_frame)
            for packet in packets:
                data_len += packet.size
                decoded_images = await decoder.decode(packet)
                for decoded_image in decoded_images:
                    np_frame = decoded_image.to_rgb().to_ndarray()
                    # await show_frame(np_frame)

        logging.info(f"size: {data_len}, crf: {codec_info.crf}")
if __name__ == '__main__':
    asyncio.run(main())