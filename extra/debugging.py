_VALUES: dict[str, str] = {}
_UPDATE_COUNTER = 0

def _print_values():
  pad_key = max(*(len(l) for l in _VALUES.keys()), 0) + 1
  print("update", _UPDATE_COUNTER)
  for k, v in sorted(_VALUES.items(), key=lambda e: e[0]): print(f"{k}:".rjust(pad_key), v)

def ddebug_value(*args):
  global _UPDATE_COUNTER
  label = " ".join(str(e) for e in args[:-1])
  _VALUES[label] = str(args[-1])
  _UPDATE_COUNTER += 1
  _print_values()  