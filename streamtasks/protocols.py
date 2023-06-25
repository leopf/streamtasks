from dataclasses import dataclass
from typing import Any
from pydantic import BaseModel

class WorkerAddresses:
  ID_DISCOVERY = 0
  COUNTER_INIT = 10000

class WorkerTopics:
  ADDRESSES_CREATED = 0
  COUNTER_INIT = 1000000

class WorkerFetchDescriptors:
  REQUEST_TOPICS = "request_topics"

class FetchRequestMessage(BaseModel):
  return_address: int
  request_id: int
  descriptor: str
  body: Any

class FetchResponseMessage(BaseModel):
  request_id: int
  body: Any

class RequestAddressesMessage(BaseModel):
  request_id: int
  count: int

class ResolveAddressesMessage(BaseModel):
  request_id: int
  addresses: list[int]

class RequestTopicsBody(BaseModel):
  count: int

class ResolveTopicBody(BaseModel):
  topics: list[int]