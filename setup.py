import re
from setuptools import setup, Extension
import pybind11
import glob

ext_modules = [ Extension(
  re.sub(r"[\/\\\\]", ".", p)[:-4],
  sources=[p],
  include_dirs=[ pybind11.get_include()],
  language='c++'
) for p in glob.glob("streamtasks/**/*.cpp", recursive=True)]

setup(ext_modules=ext_modules)
