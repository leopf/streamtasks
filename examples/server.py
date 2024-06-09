import sys
from streamtasks.bin import main_cli

main_cli(sys.argv[1:] + [ "-C" ])
