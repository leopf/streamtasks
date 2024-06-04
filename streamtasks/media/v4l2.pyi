from fractions import Fraction

class VideoCapture:
    def __init__(self, device_name: str, width: int, height: int, pixel_format: str, rate: Fraction) -> None: ...
    def read_frame(self) -> bytes: pass
    def start(self): pass
    def stop(self): pass
    def close(self): pass