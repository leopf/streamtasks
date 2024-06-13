import dbm
import os
import tempfile
from streamtasks.net.serialization import RawData

class RawDataBuffer:
  def __init__(self) -> None:
    self._key_counter: int = 0
    self._db_file = tempfile.mktemp(".db")
    self._db = dbm.open(self._db_file, "c")
    self._index_map: list[str] = []

  def __del__(self):
    self._db.close()
    os.remove(self._db_file)

  def clear(self):
    self._db.clear()
    self._index_map.clear()

  def append(self, data: RawData):
    self._index_map.append(str(self._key_counter))
    self._key_counter += 1
    self._db[self._index_map[-1]] = bytes(data.serialize())

  def popleft(self): return self.pop(0)
  def pop(self, index: int = -1):
    key = self._index_map.pop(index)
    data = RawData(self._db[key])
    del self._db[key]
    return data

  def __iter__(self):
    for key in self._index_map: yield RawData(self._db[key])
  def __len__(self): return len(self._index_map)
  def __getitem__(self, key: int): return RawData(self._db[self._index_map[key]])
  def __setitem__(self, key: int, value: RawData): self._db[self._index_map[key]] = bytes(value.serialize())
  def __delitem__(self, key: int):
    del self._db[self._index_map[key]]
    del self._index_map[key]
