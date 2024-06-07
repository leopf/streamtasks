from abc import abstractmethod
import asyncio
import itertools
from typing import Any, Optional
import pandas as pd


class PrefixMap:
  def __init__(self, length: int) -> None:
    self.length = length
    self.root: dict[str, Any] = {}

  def insert_sequence(self, seq):
    seq = list(seq)
    assert len(seq) == self.length
    current_map = self.root
    for el in seq[:-1]:
      next_map = current_map.get(el, {})
      if len(next_map) == 0: current_map[el] = next_map
      current_map = next_map
    current_map[seq[-1]] = True

  def pop_suffix(self, prefix):
    prefix = list(prefix)
    assert len(prefix) < self.length

    current_map = self.root
    for el in prefix:
      if el not in current_map: return None
      current_map = current_map[el]

    suffix = list(self._get_seq_from_map(current_map))
    self.delete_sequence(prefix + suffix)
    return tuple(suffix)

  def empty(self): return len(self.root) == 0
  def delete_sequence(self, seq: list):
    seq_maps = [self.root]
    for el in seq:
      if el not in seq_maps[-1]: return
      seq_maps.append(seq_maps[-1][el])

    pop_next = True
    for seq_map, el in list(zip(seq_maps, seq))[::-1]:
      if pop_next: seq_map.pop(el, None)
      pop_next = len(seq_map) == 0

  def _get_seq_from_map(self, m: dict):
    seq: list[Any] = []
    current_map: dict | Any = m
    while isinstance(current_map, dict):
      item = next(current_map.items().__iter__())
      seq.append(item[0])
      current_map = item[1]
    return seq


class SequenceGenerator:
  def __init__(self, elements: list) -> None:
    self.prefix_map = PrefixMap(len(elements))
    for seq in itertools.permutations(elements):
      self.prefix_map.insert_sequence(seq)

  def generate_sequence(self):
    last_elements: list[Any] = []
    max_prefix_len = self.prefix_map.length - 1
    while not self.prefix_map.empty():
      next_seq = None
      for i in range(len(last_elements)):
        next_seq = self.prefix_map.pop_suffix(last_elements[i:])
        if next_seq is not None: break
      if next_seq is None: next_seq = self.prefix_map.pop_suffix([])
      assert next_seq is not None, "Error this should not happen"
      for el in next_seq:
        yield el
        last_elements.append(el)
      if len(last_elements) > max_prefix_len: last_elements = last_elements[-max_prefix_len:]


class Simulator:
  def __init__(self) -> None:
    self.events: list[Any] = []
    self.last_event = None
    self.log_length = 20
    self.event_count = 0
    self.last_state: Optional[dict[str, Any]] = None
    self.last_eout: Optional[dict[str, Any]] = None

  def on_output(self, rout: dict[str, Any]):
    eout = self.get_output()
    self._push_event(rout, eout)
    if eout != rout:
      raise AssertionError(f"Expected output does not match the received output.\n\n{self.log_to_string()}")
  def on_idle(self): self._push_event({}, self.get_output())
  def on_event(self, event):
    self.event_count += 1
    self.last_event = event
    self.update_state(event)

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
  def update_state(self, event): pass
  @abstractmethod
  def get_output(self) -> dict[str, Any]: pass
  @abstractmethod
  def get_state(self) -> dict[str, Any]: pass

  @staticmethod
  def generate_events(selection: list):
    g = SequenceGenerator(selection)
    for event in g.generate_sequence():
      yield event

  def _push_event(self, rout: dict[str, Any], eout: dict[str, Any]):
    self.events.append({
      "EVENT": str(self.last_event),
      **{ f"STATE:{k.upper()}": str(v) for k, v in self.get_state().items() },
      **{ f"EOUT:{k.upper()}": str(v) for k, v in eout.items() },
      **{ f"ROUT:{k.upper()}": str(v) for k, v in rout.items() },
    })
    if len(self.events) > self.log_length: self.events = self.events[-self.log_length:]
