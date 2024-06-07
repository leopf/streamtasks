from fractions import Fraction
from typing import Self

class VideoCapture:
    def __init__(self, device_name: str, width: int, height: int, pixel_format: str, rate: Fraction) -> None: ...
    
    width: int
    height: int
    pixelformat: int
    framerate: Fraction
    
    def read_frame(self) -> bytes: pass
    def start(self) -> None: pass
    def stop(self) -> None: pass
    def close(self) -> None: pass