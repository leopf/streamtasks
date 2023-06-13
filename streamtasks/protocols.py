from dataclasses import dataclass

class WorkerAddresses:
  ID_DISCOVERY = 0
  COUNTER_INIT = 10000

class WorkerTopics:
  ADDRESSES_CREATED = 0
  COUNTER_INIT = 1000000

class WorkerFetchDescriptors:
  REQUEST_TOPICS = "request_topics"

@dataclass
class RequestAddressesMessage:
  request_id: int
  count: int

@dataclass
class ResolveAddressesMessage:
  request_id: int
  addresses: set[int]

@dataclass
class RequestTopicsBody:
  count: int

@dataclass
class ResolveTopicBody:
  topics: set[int]