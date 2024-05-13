import os
import platform


NODE_NAME: str = os.getenv('NODE_NAME', platform.node())
DEBUG_MEDIA = int(os.getenv("DEBUG_MEDIA", "0"))
DEBUG_SER = int(os.getenv("DEBUG_SER", "0"))
DATA_DIR = os.getenv("DATA_DIR", None) # TODO sane default 