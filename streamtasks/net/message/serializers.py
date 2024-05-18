from streamtasks.net.message.data import Serializer

"""
The core system uses the namespace 1000-1999 for content ids.
"""

def get_core_serializers() -> dict[int, Serializer]:
  serializers = []
  return { serializer.content_id: serializer for serializer in serializers }
