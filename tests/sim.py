from abc import abstractmethod
import asyncio
import itertools
import random
from typing import Any
import unittest
import pandas as pd


class Simulator:
  def __init__(self) -> None:
    self.events = []
    self.last_event = None
    self.log_length = 20
    self.event_count = 0
    self.last_state = None
    self.last_eout = None

  def on_output(self, rout: dict[str, Any]):
    eout = self.get_output()
    self._push_event(rout, eout)
    if eout != rout:
      raise AssertionError(f"Expected output does not match the received output.\n\n{self.log_to_string()}")
  def on_idle(self): self._push_event({}, self.get_output())
  def on_event(self, event, *payload):
    self.event_count += 1
    self.last_event = event
    self.update_state(event, *payload)

  def state_changed(self):
    new_state = self.get_state()
    changed = self.last_state != new_state
    self.last_state = new_state
    return changed
  def eout_changed(self):
    new_eout = self.get_output()
    changed = self.last_eout != new_eout
    self.last_eout = new_eout
    return changed
  def log_to_string(self): return f"Event count: {self.event_count}\n\n{pd.DataFrame(self.events).to_string()}"
  async def wait_or_fail(self, fut: asyncio.Future, timeout: float = 1):
    try:
      return await asyncio.wait_for(fut, timeout)
    except asyncio.TimeoutError:
      self.on_idle()
      raise Exception(f"Timed out!\n\nHere are the current logs:\n{self.log_to_string()}")

  @abstractmethod
  def update_state(self, event, *payload): pass
  @abstractmethod
  def get_output(self) -> dict[str, Any]: pass  
  @abstractmethod
  def get_state(self) -> dict[str, Any]: pass

  @staticmethod
  def generate_events(selection: list):
    subsequences = list(itertools.permutations(selection))
    rng = random.Random(42)
    rng.shuffle(subsequences)
    for seq in subsequences:
      for event in seq:
        yield event

  def _push_event(self, rout: dict[str, Any], eout: dict[str, Any]):
    self.events.append({
      "EVENT": str(self.last_event),
      **{ f"STATE:{k.upper()}": str(v) for k, v in self.get_state().items() },
      **{ f"EOUT:{k.upper()}": str(v) for k, v in eout.items() },
      **{ f"ROUT:{k.upper()}": str(v) for k, v in rout.items() },
    })
    if len(self.events) > self.log_length: self.events = self.events[-self.log_length:]