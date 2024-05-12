from streamtasks.system.fntask import fn_task
from dataclasses import dataclass
from typing import Annotated
import numpy as np

@dataclass
class BGR24RedShifterConfig:
  rate: int = 30
  width: int = 1280
  height: int = 720
  scale: float = 1.2

io_map = { v: v for v in ["rate", "width", "height"] }
default_io = { "content": "video", "pixel_format": "bgr24", "codec": "raw" }

@fn_task(thread_safe=True, config_to_input_map={ "image": io_map }, config_to_output_map=io_map)
def bgr24_red_shifter(image: Annotated[bytes, default_io], config: BGR24RedShifterConfig) -> Annotated[bytes, default_io]:
  arr = np.frombuffer(image, dtype=np.uint8).reshape((-1, 3)).astype(np.float32)
  filter = np.array([ 1, 1, config.scale ], dtype=np.float32)
  return np.minimum((arr * filter), 255).astype(np.uint8).tobytes()

if __name__ == "__main__": bgr24_red_shifter.run_sync()