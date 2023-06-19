import asyncio
import cv2
import numpy as np
from streamtasks.media.container import InputContainer
from streamtasks.media.video import VideoCodecInfo
from streamtasks.media.types import MediaPacket

async def display_frame(name: str, f: np.ndarray):
    e = asyncio.Event()
    def show():
        cv2.imshow(name, f.astype(dtype=np.uint8))
        cv2.waitKey(1)
        e.set()
    asyncio.get_running_loop().call_soon_threadsafe(show)
    await e.wait()

async def main():
    out_codec_info = VideoCodecInfo(1280, 720, 30, 'yuv420p', 'h264')
    decoder = out_codec_info.get_decoder()
    container = InputContainer("https://www.w3schools.com/html/mov_bbb.mp4", [(0, out_codec_info)])

    async for topic, packet in container.demux():
        topic, packet = (await container.decode(packet))
        assert isinstance(packet, MediaPacket) and topic == 0
        frames = await decoder.decode(packet)
        for frame in frames:
            await display_frame('frame', frame.to_rgb().to_ndarray())

if __name__ == '__main__':
    asyncio.run(main())