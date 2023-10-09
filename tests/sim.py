from abc import abstractmethod
from typing import Any
import unittest
import pandas as pd


class Simulator:
  def __init__(self) -> None:
    self.events = []
    self.last_event = None
    self.log_length = 5

    self.last_state = None
    self.last_eout = None

  def on_output(self, rout: dict[str, Any]):
    eout = self.get_output()
    self._push_event(rout, eout)
    if eout != rout:
      raise AssertionError(f"Expected output does not match the received output.\n\n{self.log_to_string()}")
  def on_idle(self): self._push_event({}, self.get_output())
  def on_event(self, event, *payload):
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
  def log_to_string(self): return pd.DataFrame(self.events).to_string()

  @abstractmethod
  def update_state(self, event, *payload): pass
  @abstractmethod
  def get_output(self) -> dict[str, Any]: pass  
  @abstractmethod
  def get_state(self) -> dict[str, Any]: pass

  def _push_event(self, rout: dict[str, Any], eout: dict[str, Any]):
    self.events.append({
      "EVENT": str(self.last_event),
      **{ f"STATE:{k.upper()}": str(v) for k, v in self.get_state().items() },
      **{ f"EOUT:{k.upper()}": str(v) for k, v in eout.items() },
      **{ f"ROUT:{k.upper()}": str(v) for k, v in rout.items() },
    })
    if len(self.events) > self.log_length: self.events = self.events[-self.log_length:]