import sys
import keyboard
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--delay", default=0.1, type=int, help="Delay between strokes.")
parser.add_argument("--combo", default="ctrl+f12", type=str, help="Key combination to be pressed to write text.")
args, _ = parser.parse_known_args()

DELAY = args.delay
COMBO = args.combo

texts = [line for line in sys.stdin.read().splitlines()]
print("Using texts:")
for idx, t in enumerate(texts):
  print(idx + 1, ". ", t)
print("")

for text in texts:
  print("Next text: ", text)
  print(f"Press '{COMBO}' to write the next text.")
  keyboard.wait(COMBO)
  keyboard.write(text, DELAY, exact=True)
