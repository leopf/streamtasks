import asyncio
from collections import deque
import os
from streamtasks.media.audio import AudioCodecInfo
from streamtasks.media.container import OutputContainer
from streamtasks.media.video import VideoCodecInfo
from tests.media import encode_all_frames, generate_audio_media_track, generate_media_frames


async def main():
    vid_path = ".data/av.webm"
    if os.path.exists(vid_path): os.remove(vid_path)
    container = await OutputContainer.open(vid_path)
    audio_codec = AudioCodecInfo("libopus", 1, 24000, "flt")
    video_codec = VideoCodecInfo(1280, 720, 30, "yuv420p", "vp8")
    audio_stream = container.add_audio_stream(audio_codec)
    video_stream = container.add_video_stream(video_codec)
    
    duration = 10
    video_frames, _ = generate_media_frames(video_codec, video_codec.frame_rate * duration)
    audio_frames, _ = await generate_audio_media_track(audio_codec, duration)
    
    video_packets = deque(await encode_all_frames(video_codec.get_encoder(), video_frames))
    audio_packets = deque(await encode_all_frames(audio_codec.get_encoder(), audio_frames))
    
    print("video packets: ", len(video_packets))
    print("audio packets: ", len(audio_packets))
    
    while len(video_packets) > 0 and len(audio_packets) > 0:
        if video_stream.ready_for_packet:
            print("mux video")
            await video_stream.mux(video_packets.popleft())
        if audio_stream.ready_for_packet:
            print("mux audio")
            await audio_stream.mux(audio_packets.popleft())
    
    await container.close()

asyncio.run(main())