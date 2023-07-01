import asyncio
import cv2
import numpy as np
from streamtasks.media.container import InputContainer
from streamtasks.media.video import VideoCodecInfo
from streamtasks.message.packets import MediaPacket
from streamtasks.media.codec import CodecInfo
import av

async def display_frame(name: str, f: np.ndarray):
    e = asyncio.Event()
    def show():
        cv2.imshow(name, f.astype(dtype=np.uint8))
        cv2.waitKey(1)
        e.set()
    asyncio.get_running_loop().call_soon_threadsafe(show)
    await e.wait()

async def main():
    out_codec_info = VideoCodecInfo(1280, 720, 30, 'yuv420p', 'h264', 4500000)
    decoder = out_codec_info.get_decoder()
    container = InputContainer("https://samplelib.com/lib/preview/mp4/sample-10s.mp4", [(0, out_codec_info)])

    async for topic, packet in container.demux():
        assert isinstance(packet, MediaPacket) and topic == 0
        frames = await decoder.decode(packet)
        for frame in frames:
            await display_frame('frame', frame.to_rgb().to_ndarray())

async def test_ctx():
    container = av.open("https://www.w3schools.com/html/mov_bbb.mp4", "r")
    ctx1 = container.streams.get({ "video": 0 })[0].codec_context
    ctx2 = CodecInfo.from_codec_context(ctx1)._get_av_codec_context("r")

    assert ctx1.type == ctx2.type
    assert ctx1.codec.long_name == ctx2.codec.long_name
    assert ctx1.width == ctx2.width
    assert ctx1.height == ctx2.height
    assert ctx1.time_base == ctx2.time_base
    assert ctx1.pix_fmt == ctx2.pix_fmt
    assert ctx1.framerate == ctx2.framerate

if __name__ == '__main__':
    asyncio.run(main())