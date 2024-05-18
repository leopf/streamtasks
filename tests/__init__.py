import os
import tempfile
import signal

_data_dir = tempfile.mkdtemp()
os.environ["DATA_DIR"] = _data_dir

def on_exit(): os.rmdir(_data_dir)
signal.signal(signal.SIGTERM, on_exit)
signal.signal(signal.SIGINT, on_exit)
