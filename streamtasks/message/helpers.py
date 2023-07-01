from streamtasks.message.data import SerializableData

def get_timestamp_from_message(data: SerializableData) -> int:
  content = data.data
  timestamp = None
  if isinstance(content, dict) and "timestamp" in content: timestamp = content["timestamp"]
  elif isinstance(content.timestamp, int): timestamp = content.timestamp
  else: raise Exception(f"could not get timestamp from message: {data}")
  if isinstance(timestamp, int): return timestamp
  if isinstance(timestamp, float): return int(timestamp)
  raise Exception(f"could not get timestamp from message: {data}")