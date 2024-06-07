from streamtasks.net.serialization import RawData

def get_timestamp_from_message(data: RawData) -> int:
  content = data.data
  timestamp = None
  if isinstance(content, dict) and "timestamp" in content: timestamp = content["timestamp"]
  elif hasattr(content, "timestamp") and isinstance(content.timestamp, int): timestamp = content.timestamp
  else: raise ValueError(f"could not get timestamp from message: {data}")
  if isinstance(timestamp, int): return timestamp
  if isinstance(timestamp, float): return int(timestamp)
  raise ValueError(f"could not get timestamp from message: {data}")

def set_timestamp_on_message(data: RawData, timestamp: int):
  data.update()
  content = data.data
  if isinstance(content, dict) and "timestamp" in content: content["timestamp"] = timestamp
  else: raise ValueError(f"could not set timestamp on message: {data}")
