import asyncio
import contextlib
from dataclasses import dataclass
import functools
import logging
from typing import Any, Callable, Annotated
import typing
from pydantic import BaseModel, TypeAdapter, ValidationError
import inspect
from streamtasks.client import Client
from streamtasks.client.topic import InTopic, OutTopic, SequentialInTopicSynchronizer
from streamtasks.connection import AutoReconnector, connect
from streamtasks.net import EndpointOrAddress, Link, Switch
from streamtasks.net.serialization import RawData
from streamtasks.message.types import NumberMessage, TextMessage, TimestampChuckMessage
from streamtasks.services.protocols import AddressNames
from streamtasks.system.configurators import EditorFields, key_to_label, static_configurator
from streamtasks.system.task import MetadataDict, Task, TaskHost, task_host_id_from_name

IOAnnotations = tuple[()] | tuple[MetadataDict] | tuple[MetadataDict, dict[str, str] | list[str]]
_IO_ANNOTATION_ADAPTER = TypeAdapter(IOAnnotations)
_DEFAULT_METADATA: MetadataDict = { "type": "ts" }
_TYPE_METADATA: dict[type, MetadataDict] = {
  int: { "content": "number" },
  float: { "content": "number" },
  str: { "content": "text" },
  bytes: {},
}

_VALUE_TO_MESSAGE: dict[type, Callable[[int, Any], BaseModel]] = {
  int: lambda timestamp, value: NumberMessage(timestamp=timestamp, value=value),
  float: lambda timestamp, value: NumberMessage(timestamp=timestamp, value=value),
  str: lambda timestamp, value: TextMessage(timestamp=timestamp, value=value),
  bytes: lambda timestamp, value: TimestampChuckMessage(timestamp=timestamp, data=value),
}

def _number_message_to_value(data: Any):
  message = NumberMessage.model_validate(data)
  return (message.timestamp, message.value)

def _text_message_to_value(data: Any):
  message = TextMessage.model_validate(data)
  return (message.timestamp, message.value)

def _chunk_message_to_value(data: Any):
  message = TimestampChuckMessage.model_validate(data)
  return (message.timestamp, message.data)

_DATA_TO_VALUE: dict[type, Callable[[Any], tuple[int, Any]]] = {
  int: _number_message_to_value,
  float: _number_message_to_value,
  str: _text_message_to_value,
  bytes: _chunk_message_to_value
}

def _validate_object_create_empty(obj_type: type[object]):
  sig = inspect.signature(obj_type)
  return all(p.default is not inspect._empty for name, p in sig.parameters.items() if name != "self")
def _input_name_to_input_key(name: str): return "_in_tid_" + name
def _output_index_to_input_key(idx: int): return "_out_tid_" + str(idx)
def _validate_io_type(t: type):
  if t not in _TYPE_METADATA: raise ValueError(f"IO type {repr(t)} is not supported!")
def _pydantic_type_from_schema(schema: dict):
  while "schema" in schema: schema = schema["schema"]
  return schema.get("type", None)
def _pydantic_schema_to_editor_fields(schema: dict):
  fields = []
  inner_schema = schema.get("schema", {})
  for field in inner_schema.get("fields", []):
    field_name = field["name"]
    field_type_name = _pydantic_type_from_schema(field)
    if field_type_name == "int": fields.append(EditorFields.number(field_name, is_int=True))
    if field_type_name == "float": fields.append(EditorFields.number(field_name))
    if field_type_name == "bool": fields.append(EditorFields.boolean(field_name))
    if field_type_name == "str": fields.append(EditorFields.text(field_name))
  return fields
def _parse_param_io_annotations(data_type: type[Annotated], metadata: MetadataDict, io_map: dict[str, str]):
  io_annotations: IOAnnotations = _IO_ANNOTATION_ADAPTER.validate_python(data_type.__metadata__)
  if len(io_annotations) >= 1: metadata.update(io_annotations[0])
  if len(io_annotations) >= 2:
    io_map.update({ v: v for v in io_annotations[1] } if isinstance(io_annotations[1], list) else io_annotations[1])
  return data_type.__origin__

@dataclass
class _FnTaskInput:
  topic: InTopic
  config: 'FnTaskInputConfig'

@dataclass
class _FnTaskOutput:
  topic: OutTopic
  config: 'FnTaskOutputConfig'

class _FnTask(Task):
  def __init__(self, client: Client, pconfig: 'ParsedTaskConfig', root_config: 'FnTaskConfig'):
    super().__init__(client)
    self.pconfig = pconfig
    self.root_config = root_config

    self.outputs = [ _FnTaskOutput(self.client.out_topic(pconfig.output_ids[idx]), output) for idx, output in enumerate(root_config.outputs) ]
    if pconfig.std_config.std_synchronized:
      sync = SequentialInTopicSynchronizer()
      input_topics = { input.name: self.client.sync_in_topic(pconfig.input_id_map[input.name], sync) for input in root_config.inputs }
    else:
      input_topics = { input.name: self.client.in_topic(pconfig.input_id_map[input.name]) for input in root_config.inputs }
    self.inputs = [ _FnTaskInput(input_topics[input.name], input) for input in root_config.inputs ]

    self.execute_lock = asyncio.Lock()

    self.param_values: dict[str, Any] = {}
    self.state = root_config.new_state()

  async def run(self):
    async with contextlib.AsyncExitStack() as exit_stack:
      for i in self.inputs:
        await exit_stack.enter_async_context(i.topic)
        await exit_stack.enter_async_context(i.topic.RegisterContext())
      for o in self.outputs:
        await exit_stack.enter_async_context(o.topic)
        await exit_stack.enter_async_context(o.topic.RegisterContext())

      self.client.start()
      await asyncio.gather(*(self._run_input(input) for input in self.inputs))

  async def execute(self, timestamp: int):
    for input in self.inputs:
      if input.config.name not in self.param_values: return

    param_values = self.param_values
    result: tuple = await self.root_config.execute(timestamp=timestamp, params=param_values, state=self.state, config=self.pconfig.fn_config)
    if len(result) != len(self.outputs): raise ValueError(f"Expected {len(self.outputs)} results, got {len(result)}!")

    for value, output in zip(result, self.outputs):
      try:
        message = _VALUE_TO_MESSAGE[output.config.data_type](timestamp, value)
        await output.topic.send(RawData(message.model_dump()))
      except ValidationError:
        logging.warning(f"Failed to create message from value on task {self.root_config.name}, output {output.config.index}!")

  async def _run_input(self, input: _FnTaskInput):
    while True:
      try:
        data = await input.topic.recv_data()
        timestamp, value = _DATA_TO_VALUE[input.config.data_type](data.data)
        async with self.execute_lock:
          self.param_values[input.config.name] = value
          await self.execute(timestamp)
      except ValidationError:
        logging.warning(f"Failed to parse message value on task {self.root_config.name}, input {input.config.name}!")


class _FnTaskHost(TaskHost):
  def __init__(self, config: 'FnTaskConfig', link: Link, register_endpoits: list[EndpointOrAddress] = []):
    super().__init__(link=link, register_endpoits=register_endpoits)
    self.config = config
    self.id = task_host_id_from_name(f"fntask_{config.name}")

  @property
  def metadata(self): return static_configurator(
      self.config.label,
      inputs=[ i.input_metadata for i in self.config.inputs ],
      outputs=[ o.output_metadata for o in self.config.outputs ],
      default_config=self.config.default_config(),
      editor_fields=self.config.editor_fields,
      config_to_input_map=self.config.config_to_input_map,
      config_to_output_map=self.config.config_to_output_map,
    )

  async def create_task(self, config: Any, topic_space_id: int | None):
    pconfig = ParsedTaskConfig(
      fn_config=self.config.config_type_adapter.validate_python(config),
      std_config=_FnTaskStdConfig.model_validate(config),
      input_id_map={ i.name: config[i.input_key] for i in self.config.inputs },
      output_ids=[ config[o.output_key] for o in self.config.outputs ]
    )

    return _FnTask(await self.create_client(topic_space_id), pconfig, self.config)

class _FnTaskStdConfig(BaseModel):
  std_synchronized: bool = True

  @staticmethod
  def editor_fields(): return [
    EditorFields.boolean("std_synchronized", "synchronized")
  ]

@dataclass
class ParsedTaskConfig:
  fn_config: Any
  std_config: _FnTaskStdConfig
  input_id_map: dict[str, int]
  output_ids: list[int]


@dataclass
class FnTaskInputConfig:
  name: str
  data_type: type
  metadata: MetadataDict
  io_map: dict[str, str]

  @property
  def input_key(self): return _input_name_to_input_key(self.name)

  @property
  def input_metadata(self): return { **self.metadata, "key": self.input_key }

  @staticmethod
  def from_parameter(param: inspect.Parameter):
    data_type = param.annotation
    metadata = { **_DEFAULT_METADATA, "label": key_to_label(param.name) }
    io_map = {}
    if typing.get_origin(data_type) is Annotated:
      data_type = _parse_param_io_annotations(data_type, metadata, io_map)
    metadata = { **_TYPE_METADATA.get(data_type, {}), **metadata }
    config = FnTaskInputConfig(name=param.name, data_type=data_type, metadata=metadata, io_map=io_map)
    config.validate()
    return config

  def validate(self): _validate_io_type(self.data_type)

@dataclass
class FnTaskOutputConfig:
  index: int
  data_type: type
  metadata: MetadataDict
  io_map: dict[str, str]

  @property
  def output_key(self): return _output_index_to_input_key(self.index)

  @property
  def output_metadata(self): return { **self.metadata, "key": self.output_key }

  @staticmethod
  def from_type(t: type, index: int):
    data_type = t
    metadata = { **_DEFAULT_METADATA, "label": f"output {index}" }
    io_map = {}
    if typing.get_origin(data_type) is Annotated:
      data_type = _parse_param_io_annotations(data_type, metadata, io_map)
    metadata = { **_TYPE_METADATA.get(data_type, {}), **metadata }
    config = FnTaskOutputConfig(index=index, data_type=data_type, metadata=metadata, io_map=io_map)
    config.validate()
    return config

  def validate(self): _validate_io_type(self.data_type)

@dataclass
class FnTaskConfig:
  fn: Callable
  name: str
  label: str
  has_timestamp: bool
  thread_safe: bool
  is_async: bool
  config_type: type[object] | None
  state_type: type[object] | None
  inputs: list[FnTaskInputConfig]
  outputs: list[FnTaskOutputConfig]

  @property
  def config_to_input_map(self) -> dict[str, dict[str, str]]: return { input.input_key: input.io_map for input in self.inputs }

  @property
  def config_to_output_map(self) -> list[dict[str, str]]: return [ output.io_map for output in self.outputs ]


  @functools.cached_property
  def config_type_adapter(self): return None if self.config_type is None else TypeAdapter(self.config_type)

  @property
  def editor_fields(self):
    type_adapter = self.config_type_adapter
    fields = []
    if type_adapter: fields.extend(_pydantic_schema_to_editor_fields(type_adapter.core_schema))
    fields.extend(_FnTaskStdConfig.editor_fields())
    return fields

  def new_state(self):
    if self.state_type is None: return None
    return self.state_type()

  def default_config(self) -> dict:
    if self.config_type is None: return {}
    config = self.config_type()
    data = self.config_type_adapter.dump_python(config)
    if not isinstance(data, dict): raise ValueError("default config must be a dict!")
    return { **_FnTaskStdConfig().model_dump(), **data}

  def validate(self):
    if self.config_type is not None:
      if not _validate_object_create_empty(self.config_type):
        raise ValueError("The config class needs to have a constructor allowing the creation of an instance without any parameters.")
      self.config_type_adapter # make sure this can be created

    if self.state_type is not None and not _validate_object_create_empty(self.config_type):
      raise ValueError("The state class needs to have a constructor allowing the creation of an instance without any parameters.")

  async def execute(self, timestamp: int, params: dict[str, Any], state: Any, config: Any) -> tuple:
    params = {**params}
    if self.has_timestamp: params["timestamp"] = timestamp
    if self.config_type is not None: params["config"] = config
    if self.state_type is not None: params["state"] = state

    fn = functools.partial(self.fn, **params)

    if self.is_async: result = await fn()
    else:
      loop = asyncio.get_running_loop()
      if self.thread_safe: result = await loop.run_in_executor(None, fn)
      else: result = fn()

    if isinstance(result, tuple): return result
    else: return (result,)

  @staticmethod
  def from_function(fn: Callable, options: dict[str, Any]):
    sig = inspect.signature(fn)

    name = fn.__name__
    label = options.get("label") or key_to_label(name)
    thread_safe = bool(options.get("thread_safe", False))
    config_type: type[object] | None = None
    state_type: type[object] | None = None
    has_timestamp = False

    params = { k: v for k, v in sig.parameters.items() }

    if "config" in params: config_type = params.pop("config").annotation
    if "state" in params: state_type = params.pop("state").annotation
    if "timestamp" in params:
      if not typing.get_origin(params.pop("timestamp").annotation) is int: raise ValueError("timestamp must be of type int!")
      has_timestamp = True

    inputs = [ FnTaskInputConfig.from_parameter(param) for param in params.values() ]

    output_type = sig.return_annotation
    if output_type is inspect._empty or output_type is None: outputs = []
    elif typing.get_origin(output_type) is tuple: outputs = [ FnTaskOutputConfig.from_type(t, idx) for idx, t in enumerate(output_type.__args__) ]
    else: outputs = [ FnTaskOutputConfig.from_type(output_type, 0) ]

    config = FnTaskConfig(
      fn=fn,
      name=name,
      label=label,
      is_async=inspect.iscoroutinefunction(fn),
      thread_safe=thread_safe,
      has_timestamp=has_timestamp,
      config_type=config_type,
      state_type=state_type,
      inputs=inputs,
      outputs=outputs
    )
    config.validate()
    config.editor_fields
    return config

class FnTaskContext:
  def __init__(self, config: FnTaskConfig) -> None:
    self.config = config

  def TaskHost(self, link: Link, register_endpoits: list[EndpointOrAddress] = []):
    return _FnTaskHost(self.config, link=link, register_endpoits=register_endpoits)

  async def run(self, to: Link | str | None = None, register_endpoits: list[EndpointOrAddress] = [AddressNames.TASK_MANAGER]):
    if isinstance(to, Link): await self.TaskHost(link=to, register_endpoits=register_endpoits).run()
    else:
      logging.info("connecting" + ("!" if to is None else " to " + to))
      switch = Switch()
      reconnector = AutoReconnector(await switch.add_local_connection(), functools.partial(connect, url=to))
      reconnector_task = asyncio.create_task(reconnector.run())
      await reconnector.wait_connected()
      logging.info("connected" + ("!" if to is None else " to " + to))
      await asyncio.gather(
        reconnector_task,
        self.TaskHost(link=await switch.add_local_connection(), register_endpoits=register_endpoits).run()
      )

  def run_sync(self, to: Link | str | None = None, register_endpoits: list[EndpointOrAddress] = [AddressNames.TASK_MANAGER]):
    asyncio.run(self.run(to, register_endpoits=register_endpoits))

def fntask(**kwargs):
  def decorator(fn: Callable): return FnTaskContext(FnTaskConfig.from_function(fn, kwargs))
  return decorator
