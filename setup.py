import platform
import re
from setuptools import setup, Extension
import pybind11
import glob

ext_kwargs = { "include_dirs": [ pybind11.get_include()], "language": "c++" }
ext_modules = [ Extension(re.sub(r"[\/\\\\]", ".", p)[:-8], sources=[p], **ext_kwargs) for p in glob.glob("streamtasks/**/*_all.cpp", recursive=True)]

p = platform.system().lower()
if p == "linux":
  ext_modules.append(Extension("streamtasks.media.v4l2", sources=[ "streamtasks/media/v4l2.cpp" ], **ext_kwargs))

setup(ext_modules=ext_modules)
