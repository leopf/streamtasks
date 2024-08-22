class NetworkAddresses:
  ID_DISCOVERY = 0
  COUNTER_INIT = 10000

class NetworkPorts:
  DISCOVERY_REQUEST_ADDRESS = 0
  DYNAMIC_START = 10000
  FETCH = 100
  ASGI = 101
  BROADCAST = 102
  SIGNAL = 103

class NetworkTopics:
  DISCOVERY_SIGNAL = 0
  ADDRESSES_CREATED = 1
  ADDRESS_NAME_ASSIGNED = 2
  COUNTER_INIT = 100000

class NetworkAddressNames:
  TASK_MANAGER = "task_manager"
  TASK_MANAGER_WEB = "task_manager_web"
  NAMED_TOPIC_MANAGER = "named_topic_manager"
  SECRET_MANAGER = "named_topic_manager"
