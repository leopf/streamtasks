import os
import pathlib
import platform
import sys


def NODE_NAME(): return os.getenv('NODE_NAME', platform.node())
def DEBUG_MEDIA(): return int(os.getenv("DEBUG_MEDIA", "0"))
def DEBUG_MIXER(): return int(os.getenv("DEBUG_MIXER", "0"))
def DEBUG_SER(): return int(os.getenv("DEBUG_SER", "0"))
def DATA_DIR():
  data_dir = os.getenv("DATA_DIR", None)
  if data_dir is None:
    if sys.platform == 'win32': base_dir = pathlib.Path(os.getenv('APPDATA'))
    elif sys.platform == 'darwin': base_dir = pathlib.Path.home() / 'Library' / 'Application Support'
    else: base_dir = pathlib.Path.home() / '.local' / 'share'
    data_dir_path = base_dir / __name__.split('.')[0]
    data_dir_path.mkdir(parents=True, exist_ok=True)
    data_dir = str(data_dir_path.absolute())
  return data_dir
def get_data_sub_dir(sub_path: str):
  dir_path = os.path.join(DATA_DIR(), sub_path)
  pathlib.Path(dir_path).mkdir(parents=True, exist_ok=True)
  return dir_path
