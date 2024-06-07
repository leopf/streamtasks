import asyncio
import contextlib
import functools
from streamtasks.client import Client
from streamtasks.client.topic import InTopic, SequentialInTopicSynchronizer
from streamtasks.system.configurators import EditorFields, multitrackio_configurator, static_configurator
from streamtasks.net.serialization import RawData
from streamtasks.message.types import NumberMessage
from streamtasks.net.messages import TopicControlData
from streamtasks.system.task import Task, TaskHost
from pydantic import BaseModel, ValidationError, model_validator
from typing import Any
import math
from lark import Lark, ParseTree, Transformer
import re

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
    | NAME "(" [expr ("," expr)*]  ")" -> func

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
  def func(self, args): return getattr(self.context, args[0])(*args[1:])
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

class CalculatorVariableConfigBase(BaseModel):
  name: str = "a"
  default_value: float = 0

class CalculatorVariableConfig(CalculatorVariableConfigBase):
  in_topic: int

class CalculatorConfigBase(BaseModel):
  variable_tracks: list[CalculatorVariableConfig] = []
  formula: str = "1"
  synchronized: bool = True

  @functools.cached_property
  def formula_ast(self): return CalculatorGrammar.parse(self.formula)

  @model_validator(mode='after')
  def validate_ast(self):
    ast = self.formula_ast
    CalculatorConfig.validate_formula(ast, set(input_var.name for input_var in self.variable_tracks))
    return self

  @staticmethod
  def validate_formula(ast: ParseTree, input_vars: set[str]):
    for var_name in input_vars:
      if not CalculatorConfig.variable_name_is_valid(var_name):
        raise ValueError(f"Invalid variable name: {var_name}, must be CNAME and not in {CalculatorEvalContext.default_input_map.keys()}")

    extractor = CalculatorNameExtractor()
    extractor.transform(ast)
    all_var_names = input_vars | CalculatorEvalContext.default_input_map.keys()
    if not extractor.var_names.issubset(all_var_names):
      raise ValueError(f"Invalid variable names: {extractor.var_names - all_var_names}")

    available_func_names = CalculatorEvalContext.__dict__.keys()
    if not extractor.func_names.issubset(available_func_names):
      raise ValueError(f"Invalid function names: {extractor.func_names - available_func_names}")

  @staticmethod
  def variable_name_is_valid(name: str) -> bool:
    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name) is None: return False
    if name in CalculatorEvalContext.default_input_map: return False
    return True

class CalculatorConfig(CalculatorConfigBase):
  out_topic: int

class CalculatorTask(Task):
  def __init__(self, client: Client, config: CalculatorConfig):
    super().__init__(client)
    self.formula_ast = config.formula_ast
    self.out_topic = self.client.out_topic(config.out_topic)
    self.var_values = { input_var.name: input_var.default_value for input_var in config.variable_tracks }

    if config.synchronized:
      sync = SequentialInTopicSynchronizer()
      self.in_topics = [
        (client.sync_in_topic(input_var.in_topic, sync), input_var.name, input_var.default_value)
        for input_var in config.variable_tracks
      ]
    else:
      self.in_topics = [
        (client.in_topic(input_var.in_topic), input_var.name, input_var.default_value)
        for input_var in config.variable_tracks
      ]

  async def run(self):
    tasks: list[asyncio.Task] = []
    try:
      async with contextlib.AsyncExitStack() as exit_stack:
        await exit_stack.enter_async_context(self.out_topic)
        await exit_stack.enter_async_context(self.out_topic.RegisterContext())
        for in_topic, var_name, default_value in self.in_topics:
          await exit_stack.enter_async_context(in_topic)
          await exit_stack.enter_async_context(in_topic.RegisterContext())
          tasks.append(asyncio.create_task(self.run_input(in_topic, var_name, default_value)))
        self.client.start()
        await asyncio.gather(*tasks)
    finally:
      for task in tasks: task.cancel()

  async def run_input(self, in_topic: InTopic, var_name: str, default_value: float):
    while True:
      data = await in_topic.recv_data_control()
      if isinstance(data, TopicControlData): self.var_values[var_name] = default_value
      else:
        try:
          message = NumberMessage.model_validate(data.data)
          self.var_values[var_name] = message.value
          await self.send_value(message.timestamp)
        except ValidationError: pass

  async def send_value(self, timestamp: int):
    result: float = CalculatorEvalTransformer(CalculatorEvalContext(self.var_values)).transform(self.formula_ast)
    await self.out_topic.send(RawData(NumberMessage(timestamp=timestamp,value=result).model_dump()))

class CalculatorTaskHost(TaskHost):
  @property
  def metadata(self): return {
    **static_configurator(
      label="calculator",
      default_config=CalculatorConfigBase().model_dump(),
      outputs=[{ "label": "output", "type": "ts", "content": "number", "key": "out_topic" }],
      config_to_output_map=[{ "formula": "label" }],
      editor_fields=[
        EditorFields.text(key="formula", label="formula"),
        EditorFields.boolean("synchronized"),
    ]),
    **multitrackio_configurator(is_input=True, track_configs=[
      {
        "key": "variable",
        "multiLabel": "variables",
        "defaultConfig": CalculatorVariableConfigBase().model_dump(),
        "defaultIO": { "type": "ts", "content": "number" },
        "ioMap": { "name": "label" },
        "editorFields": [
          EditorFields.text(key="name"),
          EditorFields.number(key="default_value"),
        ]
      }
    ])
  }
  async def create_task(self, config: Any, topic_space_id: int | None):
    return CalculatorTask(await self.create_client(topic_space_id), CalculatorConfig.model_validate(config))
