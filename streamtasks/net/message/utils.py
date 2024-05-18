from streamtasks.net.message.data import SerializableData


def get_timestamp_from_message(data: SerializableData) -> int:
  content = data.data
  timestamp = None
  if isinstance(content, dict) and "timestamp" in content: timestamp = content["timestamp"]
  elif hasattr(content, "timestamp") and isinstance(content.timestamp, int): timestamp = content.timestamp
  else: raise ValueError(f"could not get timestamp from message: {data}")
  if isinstance(timestamp, int): return timestamp
  if isinstance(timestamp, float): return int(timestamp)
  raise ValueError(f"could not get timestamp from message: {data}")

def set_timestamp_on_message(data: SerializableData, timestamp: int):
  content = data.data
  if isinstance(content, dict) and "timestamp" in content: content["timestamp"] = timestamp
  elif hasattr(content, "timestamp") and isinstance(content.timestamp, int): content.timestamp = timestamp
  else: raise ValueError(f"could not get timestamp from message: {data}")
