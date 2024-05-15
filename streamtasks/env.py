import os
import pathlib
import platform


def NODE_NAME(): return os.getenv('NODE_NAME', platform.node())
def DEBUG_MEDIA(): return int(os.getenv("DEBUG_MEDIA", "0"))
def DEBUG_SER(): return int(os.getenv("DEBUG_SER", "0"))
def DATA_DIR(): 
  data_dir = os.getenv("DATA_DIR", None)
  if data_dir is None: raise ValueError("DATA_DIR is None.")
  return data_dir
def get_data_sub_dir(sub_path: str):
  dir_path = os.path.join(DATA_DIR(), sub_path)
  pathlib.Path(dir_path).mkdir(parents=True, exist_ok=True)
  return dir_path