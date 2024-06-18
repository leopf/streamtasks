import platform
import subprocess

SCRIPT_NAME = "examples/server.py"
CMD_PREFIX = ["python", "-m", "cx_Freeze"]
packages = ["streamtasks", "uvicorn"]
subprocess.run(CMD_PREFIX + ["--script", SCRIPT_NAME, "--packages=" + ",".join(packages)])

system = platform.system().lower()
print("building exe for system:", system)
if system == "linux":
  subprocess.run(CMD_PREFIX + ["bdist_appimage", "--script", SCRIPT_NAME, "--skip-build"])
elif system == "windows":
  subprocess.run(CMD_PREFIX + ["bdist_msi", "--script", SCRIPT_NAME, "--skip-build"])
else: raise ValueError("unknown system")
