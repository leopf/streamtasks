from streamtasks.system.task import Task
from streamtasks.system.workers import TaskFactoryWorker
from streamtasks.system.types import TaskDeployment, TaskFormat, TaskStreamFormatGroup, TaskStreamFormat
from streamtasks.client import Client
from streamtasks.client.receiver import NoopReceiver
from streamtasks.message import NumberMessage, get_timestamp_from_message, SerializableData, MessagePackData
from streamtasks.streams import StreamValueTracker
from streamtasks.helpers import TimeSynchronizer
from streamtasks.comm.types import TopicControlMessage
import socket
from pydantic import BaseModel
import asyncio
import logging
from enum import Enum
from typing import Optional
import functools
import math
from lark import Lark, Transformer
import re
import itertools

CalculatorGrammar = Lark(r"""
start: expr

?expr: inline_if

?inline_if: comparsion 
    | expr "?" expr ":" expr -> inline_if

?comparsion: binary_op 
    | expr ">" expr -> gt
    | expr "<" expr -> lt
    | expr ">=" expr -> ge
    | expr "<=" expr -> le
    | expr "==" expr -> eq
    | expr "!=" expr -> ne

?binary_op: sum
    | binary_op "&" expr -> and
    | binary_op "|" expr -> or
    | binary_op "^" expr -> xor

?sum: product
    | sum "+" product -> add
    | sum "-" product -> sub

?product: exp
    | product "*" atom -> mul
    | product "/" atom -> div
    | product "%" atom -> mod

?exp: atom
    | exp "**" atom -> pow

?atom: NUMBER -> number
    | NAME -> variable
    | "-" atom -> neg
    | "+" atom -> pos
    | "!" atom -> not
    | "(" expr ")" -> group
    | NAME "(" expr ")" -> func

%import common.CNAME -> NAME
%import common.NUMBER
%import common.WS_INLINE

%ignore WS_INLINE

""")

# defines all helper functions for the calculator language and provides the variables
class CalculatorEvalContext:
  default_input_map = {
    "pi": math.pi,
    "e": math.e
  }

  def __init__(self, input_map: dict[str, float]): self.input_map = { **self.default_input_map, **input_map }

  def __getitem__(self, key): return self.input_map[key]
  def sin(self, x): return math.sin(x)
  def cos(self, x): return math.cos(x)
  def tan(self, x): return math.tan(x)
  def asin(self, x): return math.asin(x)
  def acos(self, x): return math.acos(x)
  def atan(self, x): return math.atan(x)
  def atan2(self, y, x): return math.atan2(y, x)
  def sinh(self, x): return math.sinh(x)
  def cosh(self, x): return math.cosh(x)
  def tanh(self, x): return math.tanh(x)
  def asinh(self, x): return math.asinh(x)
  def acosh(self, x): return math.acosh(x)
  def atanh(self, x): return math.atanh(x)
  def log(self, x): return math.log(x)
  def log2(self, x): return math.log2(x)
  def log10(self, x): return math.log10(x)
  def exp(self, x): return math.exp(x)
  def sqrt(self, x): return math.sqrt(x)
  def floor(self, x): return math.floor(x)
  def ceil(self, x): return math.ceil(x)
  def round(self, x): return round(x)
  def abs(self, x): return abs(x)
  def min(self, *args): return min(*args)
  def max(self, *args): return max(*args)

def variable_name_is_valid(name: str) -> bool:
  if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name) is None: return False
  if name in CalculatorEvalContext.default_input_map: return False
  return True

# takes an input map and transforms bools to floats. Any float > 0.5 is considered True, otherwise False
class CalculatorEvalTransformer(Transformer):
  def __init__(self, context: CalculatorEvalContext):
    super().__init__()
    self.context = context

  def start(self, args): return args[0]
  def number(self, args): return float(args[0])
  def variable(self, args): return self.context[args[0]]
  def neg(self, args): return -args[0]
  def pos(self, args): return args[0]
  def not_(self, args): return 0.0 if args[0] > 0.5 else 1.0
  def group(self, args): return args[0]
  def func(self, args): return getattr(self.context, args[0])(args[1])
  def add(self, args): return args[0] + args[1]
  def sub(self, args): return args[0] - args[1]
  def mul(self, args): return args[0] * args[1]
  def div(self, args): return args[0] / args[1]
  def mod(self, args): return args[0] % args[1]
  def pow(self, args): return args[0] ** args[1]
  def and_(self, args): return 1.0 if args[0] > 0.5 and args[1] > 0.5 else 0.0
  def or_(self, args): return 1.0 if args[0] > 0.5 or args[1] > 0.5 else 0.0
  def xor(self, args): return 1.0 if args[0] > 0.5 != args[1] > 0.5 else 0.0
  def gt(self, args): return 1.0 if args[0] > args[1] else 0.0
  def lt(self, args): return 1.0 if args[0] < args[1] else 0.0
  def ge(self, args): return 1.0 if args[0] >= args[1] else 0.0
  def le(self, args): return 1.0 if args[0] <= args[1] else 0.0
  def eq(self, args): return 1.0 if args[0] == args[1] else 0.0
  def ne(self, args): return 1.0 if args[0] != args[1] else 0.0
  def inline_if(self, args): return args[1] if args[0] > 0.5 else args[2]

class CalculatorNameExtractor(Transformer):
  def __init__(self):
    super().__init__()
    self.var_names = set()
    self.func_names = set()

  def start(self, args): return self.var_names
  def variable(self, args): self.var_names.add(args[0])
  def func(self, args): self.func_names.add(args[0])

class CalculatorInputConfig(BaseModel):
  name: str
  default_value: Optional[float]

class CalculatorTask(Task):
  def __init__(self, client: Client, deployment: TaskDeployment):
    super().__init__(client)
    self.setup_done = asyncio.Event()
    self.deployment = deployment

  async def start_task(self):
    try:
      return await asyncio.gather(
        self._setup(),
        self._run_receiver()
      )
    finally:
      await self.output_tracker.set_topic(None)
      for input_tracker in self.input_trackers: await input_tracker.set_topic(None)
  
  async def _setup(self):
    await self._setup_deployment()
    self.setup_done.set()

  async def _run_receiver(self):
    await self.setup_done.wait()
    async with self.client.provide_context([self.output_topic_id]):
      async with self.client.get_topics_receiver(self.input_topic_ids) as input_recv:
        async for topic_id, data, control in input_recv:
          value_tracker = self.input_value_trackers.get(topic_id, None)
          if value_tracker is None: continue
          if control is not None: self._process_control(topic_id, control)
          elif data is not None: self._process_data(topic_id, data)
            
  async def _process_control(self, topic_id: int, control: TopicControlMessage):
    tracker: StreamValueTracker = self.input_value_trackers.get(topic_id, None)
    if tracker is None: return
    if control.paused: tracker.set_stale()

  async def _process_data(self, topic_id: int, data: SerializableData):
    tracker: StreamValueTracker = self.input_value_trackers.get(topic_id, None)
    if tracker is None: return
    try:
      message: NumberMessage = NumberMessage.parse_obj(data.data)
      tracker.add(message.timestamp, message.value)
      await self._send_calculated_output(message.timestamp)
    except: logging.error(f"Failed to parse data from topic {topic_id}")

  async def _send_calculated_output(self, timestamp: int):
    input_map = {}
    for topic_id, input_config in self.input_configs:
      if topic_id in self.input_value_trackers: value = self.input_value_trackers[topic_id].pop(timestamp, input_config.default_value)
      else: value = input_config.default_value
      input_map[input_config.name] = value
    output_value = CalculatorEvalTransformer(CalculatorEvalContext(input_map)).transform(self.formula_ast)
    await self.client.send_stream_data(self.output_topic_id, NumberMessage(timestamp=timestamp, value=output_value))

  async def _setup_deployment(self):
    topic_id_map = self.deployment.topic_id_map
    
    input_configs = self.deployment.config["input_configs"]
    self.input_topic_ids = [ topic_id_map[input.topic_id] for input in self.deployment.stream_groups[0].inputs]
    self.input_value_trackers = { topic_id: StreamValueTracker() for topic_id in self.input_topic_ids }
    self.input_configs = [ (topic_id, CalculatorInputConfig.parse_obj(config)) for topic_id, config in zip(self.input_topic_ids, input_configs) ]
    self.output_topic_id = topic_id_map[self.deployment.stream_groups[0].outputs[0].topic_id]
    self.formula_ast = CalculatorGrammar.parse(self.deployment.config["formula"]) 

    # validate input configs
    var_names = [ input_config.name for input_config in self.input_configs ]
    for var_name in var_names: 
      if not variable_name_is_valid(var_name): raise Exception(f"Invalid variable name: {var_name}, must be CNAME and not in {CalculatorEvalContext.default_input_map.keys()}")
    extractor = CalculatorNameExtractor()
    extractor.transform(self.formula_ast)
    all_var_names = set(itertools.chain(var_names, CalculatorEvalContext.default_input_map.keys()))
    if not extractor.var_names.issubset(all_var_names): raise Exception(f"Invalid variable names: {used_var_names - all_var_names}")
    available_func_names = CalculatorEvalContext.__dict__.keys()
    if not extractor.func_names.issubset(available_func_names): raise Exception(f"Invalid function names: {used_func_names - available_func_names}")

class CalculatorTaskFactoryWorker(TaskFactoryWorker):
  async def create_task(self, deployment: TaskDeployment): return CalculatorTask(await self.create_client(), deployment)
  @property
  def config_script(self): return ""
  @property
  def task_format(self): return TaskFormat(
    task_factory_id=self.id,
    label="Calculator",
    hostname=socket.gethostname(),
    stream_groups=[
      TaskStreamFormatGroup(
        inputs=[TaskStreamFormat(label="x"), TaskStreamFormat(label="y")],    
        outputs=[TaskStreamFormat(label="output")]      
      )
    ]
  )