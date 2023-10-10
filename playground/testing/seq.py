import itertools

class PrefixMap:
  def __init__(self, l) -> None:
    self.l = l
    self.root = {}

  def insert_sequence(self, seq):
    seq = list(seq)
    assert len(seq) == self.l
    current_map = self.root
    for el in seq[:-1]:
      next_map = current_map.get(el, {})
      if len(next_map) == 0: current_map[el] = next_map
      current_map = next_map
    current_map[seq[-1]] = True

  def pop_suffix(self, prefix):
    prefix = list(prefix)
    assert len(prefix) < self.l
    
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
    seq = []
    current_map = m
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
    last_elements = []
    max_prefix_len = self.prefix_map.l - 1
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

elements = [ "1", "2", "3", "4", "5", "6", "7", "8" ]
g = SequenceGenerator(elements)
count = 0
sequence = "".join(list(g.generate_sequence()))
# print(sequence)
naive_len = 0
for p in itertools.permutations(elements):
  p = "".join(p)
  naive_len += len(p)
  if p not in sequence: print("missing: ", p)
# for el in g.generate_sequence(): count += 1
# print("seq len: ", count)

print(f"len is {len(sequence)}/{naive_len} = {len(sequence)/naive_len} ")