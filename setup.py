import re
from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension
import glob

extra_args = { "extra_compile_args": ["-std=c++17"] }
ext_modules = [ Pybind11Extension(re.sub(r"[\/\\\\]", ".", p)[:-8], sources=[p], **extra_args) for p in glob.glob("streamtasks/**/*_all.cpp", recursive=True)]
setup(ext_modules=ext_modules)
