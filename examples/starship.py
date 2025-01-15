import asyncio
from dataclasses import dataclass
import re
from typing import Annotated
from streamtasks.bin import apply_args
from streamtasks.media.util import pixel_format_to_pil_mode
from streamtasks.services.constants import NetworkAddressNames
from streamtasks.system.fntask import fntask
from streamtasks.system.builder import SystemBuilder, TaskPriorities
import pytesseract
from PIL import Image

@dataclass
class OCRTaskConfig:
  rate: int = 30
  width: int = 1280
  height: int = 720
  is_ship: bool = True

pixel_format = "rgb24"
io_map = ["rate", "width", "height"]
default_io = { "content": "video", "pixel_format": pixel_format, "codec": "raw" }

counter = 0

@fntask(label="Starship telemetry tracker", thread_safe=True)
def starship_telemetry(data: Annotated[bytes, default_io, io_map], config: OCRTaskConfig) -> tuple[Annotated[int, {"label": "altitude"}], Annotated[int, {"label": "speed"}]]:
  global counter
  img = Image.frombytes(pixel_format_to_pil_mode(pixel_format), (config.width, config.height), data)
  left_off, right_off = 0, config.width//3
  if not config.is_ship: left_off, right_off = left_off+config.width*2//3, right_off+config.width*2//3
  img = img.crop((left_off, config.height*2//3, right_off, config.height))

  tel_text = str(pytesseract.image_to_string(img, config="--psm 6")).lower()

  try: alt_v = int(next(re.finditer(r"altitude\s+(\d+)", tel_text)).group(1))
  except: alt_v = 0
  try: speed_v = int(next(re.finditer(r"speed\s+(\d+)", tel_text)).group(1))
  except: speed_v = 0

  return alt_v, speed_v

async def main():
  builder = SystemBuilder()
  await apply_args(builder)
  await builder.start_worker(starship_telemetry.TaskHost(register_endpoits=[NetworkAddressNames.TASK_MANAGER]), TaskPriorities.Low)
  await builder.wait_done()

if __name__ == "__main__":
  asyncio.run(main())
