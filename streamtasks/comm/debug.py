import random

MESSAGE_ID_MAP = {}
MESSAGE_ACTIONS = {}

def trace_message_action(actor_name, message, action):
  message_id = id(message)
  if message_id not in MESSAGE_ID_MAP:
    MESSAGE_ID_MAP[message_id] = random.randint(0, 0xFFFFFFFF)
  message_index = MESSAGE_ID_MAP[message_id]
  if message_index not in MESSAGE_ACTIONS:
    MESSAGE_ACTIONS[message_index] = []
  MESSAGE_ACTIONS[message_index].append((actor_name, action))

def register_messages_equal(old, new):
  old_id = id(old)
  new_id = id(new)
  if old_id not in MESSAGE_ID_MAP:
    MESSAGE_ID_MAP[old_id] = random.randint(0, 0xFFFFFFFF)
  MESSAGE_ID_MAP[new_id] = MESSAGE_ID_MAP[old_id]

def trace_clear():
  MESSAGE_ID_MAP.clear()
  MESSAGE_ACTIONS.clear()

def async_param_trace(action, actor_prefix):
  actor_name = actor_prefix + "".join(random.choices('abcdefghijklmnopqrstuvwxyz', k=8))
  def dec(fn):
    def wrapper(*args, **kwargs):
      re
      return fn(*args, **kwargs)
    return wrapper