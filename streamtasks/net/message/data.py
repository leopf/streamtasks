from typing import Union, Any
import msgpack

class RawData:
  def __init__(self, data: Union[Any, memoryview]): self._data, self._raw = (data, None) if not isinstance(data, (memoryview, bytes, bytearray)) else (None, data)

  @property
  def data(self):
    if self._data is None: self._data = self.deserialize()
    return self._data

  def serialize(self) -> memoryview: return self._raw if self._raw is not None else memoryview(self._serialize())
  def deserialize(self) -> Any: return self._data if self._data is not None else self._deserialize()
  def update(self): self._raw = None
  def copy(self): return self.__class__(memoryview(self.serialize()))

  def _deserialize(self) -> Any: return msgpack.unpackb(self._raw)
  def _serialize(self) -> bytes: return msgpack.packb(self._data)
