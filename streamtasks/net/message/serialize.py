import streamtasks.net.message.types as messages
import msgpack

MESSAGES: list[type[messages.Message]] = [
  messages.TopicDataMessage,
  messages.TopicControlMessage,
  messages.AddressedMessage,
  messages.AddressesChangedMessage,
  messages.InTopicsChangedMessage,
  messages.OutTopicsChangedMessage,
]

MESSAGE_TYPE_ID_MAP = { t: idx for idx, t in enumerate(MESSAGES) }
TYPE_ID_MESSAGE_MAP = { idx: t for idx, t in enumerate(MESSAGES) }

def serialize_message(message: messages.Message) -> bytes: return msgpack.packb({ **message.as_dict(), "_id": MESSAGE_TYPE_ID_MAP[type(message)] })
def deserialize_message(raw: bytes) -> messages.Message:
  data = msgpack.unpackb(raw)
  return TYPE_ID_MESSAGE_MAP[data.pop("_id")].from_dict(data)
