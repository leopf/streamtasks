import sys

_VALUES: dict[str, str] = {}
_UPDATE_COUNTER = 0

def _print_values():
  pad_key = max(*(len(l) for l in _VALUES.keys()), 0) + 1
  lines = [
    "-" * 25,
    "update " + str(_UPDATE_COUNTER),
  ]
  for k, v in sorted(_VALUES.items(), key=lambda e: e[0]): lines.append(f"{k}:".rjust(pad_key) + " " + str(v))
  sys.stdout.write("\n".join(lines))
  sys.stdout.write("\n")
  sys.stdout.flush()

def ddebug_value(*args):
  global _UPDATE_COUNTER
  label = " ".join(str(e) for e in args[:-1])
  _VALUES[label] = str(args[-1])
  _UPDATE_COUNTER += 1
  _print_values()
