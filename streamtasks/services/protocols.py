from typing import Optional
from pydantic import BaseModel


class WorkerAddresses:
  ID_DISCOVERY = 0
  COUNTER_INIT = 10000


class WorkerPorts:
  DISCOVERY_REQUEST_ADDRESS = 0
  DYNAMIC_START = 10000
  FETCH = 100
  ASGI = 101
  BROADCAST = 102
  SIGNAL = 103


class WorkerTopics:
  DISCOVERY_SIGNAL = 0
  ADDRESSES_CREATED = 1
  ADDRESS_NAME_ASSIGNED = 2
  COUNTER_INIT = 100000


class WorkerRequestDescriptors:
  REQUEST_TOPICS = "request_topics"

  REQUEST_ADDRESSES = "request_addresses"

  RESOLVE_ADDRESS = "resolve_address_name"
  REGISTER_ADDRESS = "register_address_name"

  REGISTER_TOPIC_SPACE = "register_topic_space"
  GET_TOPIC_SPACE = "get_topic_space"
  DELETE_TOPIC_SPACE = "delete_topic_space"

class AddressNames:
  TASK_MANAGER = "task_manager"
  TASK_MANAGER_WEB = "task_manager_web"

class TopicSpaceRequestMessage(BaseModel):
  id: int

class RegisterTopicSpaceRequestMessage(BaseModel):
  topic_ids: set[int]
  
class TopicSpaceResponseMessage(BaseModel):
  id: int
  topic_id_map: dict[int, int]

class GenerateAddressesRequestMessageBase(BaseModel):
  count: int

class GenerateAddressesRequestMessage(GenerateAddressesRequestMessageBase):
  request_id: int

class GenerateAddressesResponseMessageBase(BaseModel):
  addresses: list[int]

class GenerateAddressesResponseMessage(GenerateAddressesResponseMessageBase):
  request_id: int

class GenerateTopicsRequestBody(BaseModel):
  count: int


class GenerateTopicsResponseBody(BaseModel):
  topics: list[int]


class ResolveAddressRequestBody(BaseModel):
  address_name: str


class ResolveAddressResonseBody(BaseModel):
  address: Optional[int] = None


class RegisterAddressRequestBody(BaseModel):
  address_name: str
  address: Optional[int] = None


class AddressNameAssignmentMessage(BaseModel):
  address_name: str
  address: Optional[int] = None