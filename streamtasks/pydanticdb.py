import copy
import os
from typing import Generic, Iterable, TypeVar
from pydantic import BaseModel, TypeAdapter

T = TypeVar("T", bound=BaseModel)

class PydanticDB(Generic[T]):
  def __init__(self, model: type[T], filename: str) -> None:
    self._list_model = TypeAdapter(list[model])
    self._entries: list[T] = []
    self._filename = filename
    if os.path.exists(filename): self.load()

  @property
  def entries(self): return copy.deepcopy(self._entries)

  def save(self):
    with open(self._filename, "wb") as fd: fd.write(self._list_model.dump_json(self._entries))

  def load(self):
    with open(self._filename, "rb") as fd: self._entries = self._list_model.validate_json(fd.read())

  def update(self, entries: Iterable[T]): self._entries = list(entries)
