

import inspect
from typing import Any, Literal, Optional, Union, get_origin, Iterator
from abc import ABC, abstractmethod
from dataclasses import dataclass
import itertools

from pydantic import BaseModel

@dataclass
class StreamType:
    label: str
    
    pre_processor: Optional[callable] = None
    
    # stream data
    content_type: Optional[str] = None
    encoding: Optional[str] = None
    extra: Optional[dict[str, Any]] = None

class StreamTypeNode(ABC):
    @abstractmethod
    def get_stream_types(self, name: str) -> Iterator[StreamType]: pass
    
    # gets values in pre processed form
    @abstractmethod
    def reconstruct(self, values: iter) -> Any: pass

class StreamTypeLeafNode:
    def __init__(self, t: str):
        self.type: Literal["text", "int", "float"] = t 
        
    @property
    def content_type(self):
        if self.type == "text": return "text"
        if self.type == "int": return "number"
        if self.type == "float": return "number"
        raise ValueError(f"Unknown type: {self.type}")
        
    @property
    def pre_processor(self):
        if self.type == "text": return None
        if self.type == "int": return int
        if self.type == "float": return float
        
    def get_stream_types(self, name: str) -> Iterator[StreamType]:
        yield StreamType(
            label=name,
            pre_processor=self.pre_processor,
            content_type=self.content_type,
        )
    
    def reconstruct(self, values: iter) -> Any:
        v = next(values)
        if self.type == "text" and isinstance(v, str): return v
        if self.type == "int" and isinstance(v, int): return v
        if self.type == "float" and isinstance(v, float): return v
        raise ValueError(f"Invalid value {v} for type {self.type}")

class StreamTypeOptionalNode:
    def __init__(self, item: StreamTypeNode):
        self.item = item
        
    def get_stream_types(self, name: str) -> Iterator[StreamType]:
        yield from self.item.get_stream_types(f"{name}?")
        
    def reconstruct(self, values: iter) -> Any:
        try: return self.item.reconstruct(values)
        except: return None

class StreamTypeDictNode:
    def __init__(self, items: list(tuple[str, StreamTypeNode])):
        self.items = items
        
    def get_stream_types(self, name: str) -> Iterator[StreamType]:
        return itertools.chain.from_iterable(
            item.get_stream_types(f"{name}:{key}")
            for key, item in self.items
        )
        
    def reconstruct(self, values: iter) -> Any:
        error_info = None
        
        result = {}
        
        for i in range(len(self.items)):
            try:
                key, item = self.items[i]
                result[key] = item.reconstruct(values)
            except Exception as e:
                error_info = (e, i)
                break
        
        if error_info is not None:
            for i in range(error_info[1] + 1, len(self.items)):
                try:
                    key, item = self.items[i]
                    item.reconstruct(values)
                except: pass

            raise error_info[0]
        
        return result
            
class StreamTypeTupleNode:
    def __init__(self, items: tuple[StreamTypeNode]):
        self.items = items
        
    def get_stream_types(self, name: str) -> Iterator[StreamType]:
        return itertools.chain.from_iterable(
            item.get_stream_types(f"{name}:{i}")
            for i, item in enumerate(self.items)
        )
        
    def reconstruct(self, values: iter) -> Any:
        error_info = None
        
        result = []
        
        for i in range(len(self.items)):
            try:
                item = self.items[i]
                result.append(item.reconstruct(values))
            except Exception as e:
                error_info = (e, i)
                break
        
        if error_info is not None:
            for i in range(error_info[1] + 1, len(self.items)):
                try:
                    item = self.items[i]
                    item.reconstruct(values)
                except: pass

            raise error_info[0]
        
        return tuple(result)
        
def type_def_to_stream_types(t):
    if t == str: return StreamTypeLeafNode("text")
    if t == int: return StreamTypeLeafNode("int")
    if t == float: return StreamTypeLeafNode("float")
    
    t_origin = get_origin(t)
    
    if t_origin == tuple: return StreamTypeTupleNode(tuple(type_def_to_stream_types(it) for it in t.__args__))
    
    # check for Optional
    if t_origin == Union and len(t.__args__) == 2 and t.__args__[1] == type(None): return StreamTypeOptionalNode(type_def_to_stream_types(t.__args__[0]))
    
    raise ValueError(f"Invalid type {t}. Must be one of str, int, float, tuple")
    
def function_sig_to_stream_types(sig):
    params = StreamTypeDictNode(list((name, type_def_to_stream_types(param.annotation)) for name, param in sig.parameters.items() if name != "config"))
    return_type = type_def_to_stream_types(sig.return_annotation)
    
    return params, return_type

def pre_process_values(values: list, stream_types: list[StreamType]):
    for v, stream_type in zip(values, stream_types):
        try: yield stream_type.reconstruct(v)
        except: yield v

class TestConfig(BaseModel):
    name: str
    value: int = 0

def test_task(value: Optional[float], config: TestConfig, *args: tuple[int, str]) -> float:
    return value + 1

from pprint import pprint

p, r = function_sig_to_stream_types(inspect.signature(test_task))
pv, rv = list(p.get_stream_types("")), list(r.get_stream_types(""))

print(rv, pv)

test_values = [
    None, 1, "hello"
]

assert len(pv) == len(test_values)

pp_test_values = pre_process_values(test_values, pv)
print("reconstructed", p.reconstruct(iter(pp_test_values)))
