python -m venv .venv
source .venv/bin/activate
pip install .[media] cx_Freeze
python -m cx_Freeze bdist_appimage --script examples/server.py