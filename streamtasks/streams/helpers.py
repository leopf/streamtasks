class StreamValueTracker:
  def __init__(self):
    self.values = []
    self._stale = False
    self._in_timeframe = False
  def pop(self, timestamp: int, default=None):
    if len(self.values) == 0 or self.values[0][0] < timestamp: 
      self._in_timeframe = False
      return default
    self._in_timeframe = True
    while len(self.values) > 1 and self.values[1][0] <= timestamp: self.values.pop(0)
    if len(self.values) == 1 and self._stale: return default
    return self.values[0][1]
  def add(self, timestamp: int, value: Any):
    self._stale = False
    self.values.append((timestamp, value))
    self.values.sort(key=lambda x: x[0])
  def set_stale(self): self._stale = True
  def has_value(self, predicate: Callable[[int, Any], bool], default_value=None) -> bool: 
    if len(self.values) == 0: return predicate(0, default_value)
    if len(self.values) == 1 and self._stale and self._in_timeframe: return predicate(self.values[0][0], default_value)
    return any(predicate(*entry) for entry in self.values)