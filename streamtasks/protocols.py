from dataclasses import dataclass
from typing import Any, Optional
from pydantic import BaseModel

class WorkerAddresses:
  ID_DISCOVERY = 0
  COUNTER_INIT = 10000

class WorkerTopics:
  ADDRESSES_CREATED = 0
  COUNTER_INIT = 1000000

class WorkerFetchDescriptors:
  GENERATE_TOPICS = "request_topics"
  RESOLVE_ADDRESS = "resolve_address_name"
  REGISTER_ADDRESS = "register_address_name"


class GenerateAddressesRequestMessage(BaseModel):
  request_id: int
  count: int

class GenerateAddressesResponseMessage(BaseModel):
  request_id: int
  addresses: list[int]

class GenerateTopicsRequestBody(BaseModel):
  count: int

class GenerateTopicsResponseBody(BaseModel):
  topics: list[int]

class ResolveAddressRequestBody(BaseModel):
  address_name: str

class ResolveAddressResonseBody(BaseModel):
  address: Optional[int]

class RegisterAddressRequestBody(BaseModel):
  address_name: str
  address: Optional[int]