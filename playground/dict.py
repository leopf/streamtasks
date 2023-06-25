from pydantic import BaseModel
from pydantic.dataclasses import dataclass
import json


class TestModel(BaseModel):
    la: int

data = TestModel.parse_obj({"la":1})
print(data.dict())