from functools import cached_property
from streamtasks.system.helpers import validate_stream_config
from streamtasks.system.task import Task, TaskFactoryWorker
from streamtasks.system.types import DeploymentTaskScaffold, RPCTaskConnectRequest, DeploymentTask, RPCTaskConnectRequest, TaskStreamConfig, TaskStreamGroup, TaskInputStream, TaskOutputStream, DeploymentTask
import socket
from pydantic import BaseModel
from typing import Optional
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

def validate_formula(formula_ast, input_var_names):
  for var_name in input_var_names: 
    if not variable_name_is_valid(var_name): raise Exception(f"Invalid variable name: {var_name}, must be CNAME and not in {CalculatorEvalContext.default_input_map.keys()}")
  extractor = CalculatorNameExtractor()
  extractor.transform(formula_ast)
  all_var_names = set(itertools.chain(input_var_names, CalculatorEvalContext.default_input_map.keys()))
  if not extractor.var_names.issubset(all_var_names): raise Exception(f"Invalid variable names: {extractor.var_names - all_var_names}")
  available_func_names = CalculatorEvalContext.__dict__.keys()
  if not extractor.func_names.issubset(available_func_names): raise Exception(f"Invalid function names: {extractor.func_names - available_func_names}")

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
  fallback_value: Optional[float] = None

def variable_name_ganerator():
  synbols = "abcdefghijklmnopqrstuvwxyz"
  counts = [0]
  while True:
    name = "".join(synbols[i] for i in counts)
    yield name
    
    counts[-1] += 1
    for i in range(len(counts) - 1, -1, -1):
      if counts[i] >= len(synbols):
        counts[i] = 0
        if i == 0: counts.insert(0, 0)
        else: counts[i - 1] += 1
      else: break

class CalculatorTask(Task):
  @classmethod
  def name(cls): return "Calculator"
  @classmethod
  def task_scaffold(cls): return DeploymentTaskScaffold(
    config={
      "formula": "",
    },
    stream_groups=[
      TaskStreamGroup(
        inputs=[],    
        outputs=[TaskOutputStream(label="output")]      
      )
    ]
  )
  @classmethod
  async def rpc_connect(cls, req: RPCTaskConnectRequest) -> Optional[DeploymentTask]:
    if req.output_stream is not None:
      validate_stream_config(req.output_stream, TaskStreamConfig(content_type="number"), "Input must be a number")
      topic_id = req.output_stream.topic_id
    else: topic_id = None
    for input_stream in req.task.stream_groups[0].inputs:
      if req.input_id == input_stream.ref_id:
        input_stream.topic_id = topic_id
        break
    return req.task
  
  @cached_property
  def topic_label_map(self):
    return {
      stream.label: stream.topic_id
      for stream in self.deployment.stream_groups[0].inputs + self.deployment.stream_groups[0].outputs
    }
  
  async def setup(self):
    self.formula_ast = CalculatorGrammar.parse(self.deployment.config["formula"])
    input_configs = [ CalculatorInputConfig.model_validate(config) for config in self.deployment.config["input_configs"] ]
    validate_formula(self.formula_ast, [ config.name for config in input_configs ])
    
  async def on_changed(self, timestamp: int, **kwargs):
    input_map = None
    
  
class CalculatorTaskFactoryWorker(TaskFactoryWorker):
  async def create_task(self, deployment: DeploymentTask): return CalculatorTask(await self.create_client(), deployment)
  async def rpc_connect(self, req: RPCTaskConnectRequest) -> DeploymentTask: return req.task
  @property
  def task_template(self): return DeploymentTask(
    task_factory_id=self.id,
    config={
      "label": "Calculator",
      "hostname": socket.gethostname(),
    },
    stream_groups=[
      TaskStreamGroup(
        inputs=[TaskInputStream(label="x"), TaskInputStream(label="y")],    
        outputs=[TaskOutputStream(label="output")]      
      )
    ]
  )