import platform
import re
from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension
import glob

extra_compile_args = []
if platform.system() == "Windows": extra_compile_args.append("/std:c++17")
else: extra_compile_args.append("-std=c++17")

extra_args = { "extra_compile_args": extra_compile_args }
ext_modules = [ Pybind11Extension(re.sub(r"[\/\\\\]", ".", p)[:-8], sources=[p], **extra_args) for p in glob.glob("streamtasks/**/*_all.cpp", recursive=True)]
setup(ext_modules=ext_modules)
