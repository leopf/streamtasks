import os
import pathlib
import platform


NODE_NAME: str = os.getenv('NODE_NAME', platform.node())
DEBUG_MEDIA = int(os.getenv("DEBUG_MEDIA", "0"))
DEBUG_SER = int(os.getenv("DEBUG_SER", "0"))
DATA_DIR = os.getenv("DATA_DIR", None) # TODO sane default 

def get_data_sub_dir(sub_path: str):
  if DATA_DIR is None: raise ValueError("DATA_DIR is None.")
  dir_path = os.path.join(DATA_DIR, sub_path)
  pathlib.Path(dir_path).mkdir(parents=True, exist_ok=True)
  return dir_path