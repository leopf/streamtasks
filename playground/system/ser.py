from streamtasks.system.types import RPCTaskConnectRequest
import json

s = ('{"input_id":"d667e5f7-0ed3-4152-b0a9-0f949748aa9f","output_stream":{"label":"output","content_type":null,"encoding":null,"extra":null,"topic_id":"78a4265b-0791-4801-a737-e40a3973cb0b"},"task":{"id":"a2a8b49b-23ad-4fff-8a97-0eb3074b4d07","task_factory_id":"da1d5036-a80e-4087-a12a-7c9460bd3089","config":{"label":"Gate","hostname":"pfobmachine","position":{"x":398.4070640515172,"y":407.5}},"stream_groups":[{"inputs":[{"label":"input","content_type":null,"encoding":null,"extra":null,"topic_id":null,"ref_id":"d667e5f7-0ed3-4152-b0a9-0f949748aa9f"},{"label":"gate","content_type":"number","encoding":null,"extra":null,"topic_id":null,"ref_id":"0689b968-8884-49a6-95d5-c08c2c5ea7aa"}],"outputs":[{"label":"output","content_type":null,"encoding":null,"extra":null,"topic_id":"edb9df1a-5fb1-4f34-b463-6135ea7696f0"}]}],"topic_id_map":{}}}')
d = json.loads(s)
print(RPCTaskConnectRequest.parse_raw(s))
