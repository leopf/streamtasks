import inspect
from streamtasks.asgi import Optional
from streamtasks.client import Client
from streamtasks.comm import Connection
from streamtasks.system.helpers import Optional
from streamtasks.system.protocols import Optional
from streamtasks.system.store import DeploymentTask, Optional, RPCTaskConnectRequest
from streamtasks.system.task import Task
from streamtasks.system.types import DeploymentTask, Optional, RPCTaskConnectRequest, TaskInputStream, TaskStreamGroup
from streamtasks.system.task import TaskFactoryWorker
from pydantic import BaseModel
from dataclasses import dataclass
from typing import Any, Union, Optional, Literal, Tuple, get_origin
import itertools

TaskTypeSingle = Literal["string", "int", "float"]
TaskType = Union[TaskTypeSingle, tuple['TaskType', ...]]

def get_signature_type(t: type):
    if t == str:
        return "string"
    elif t == int:
        return "int"
    elif t == float:
        return "float"
    elif get_origin(t) == tuple:
        return tuple(get_signature_type(it) for it in t.__args__)
    else:
        raise ValueError(f"Invalid type {t}. Must be one of str, int, float, tuple")

@dataclass
class FunctionTaskType:
    name: TaskTypeSingle
    
    def prepare_value(self, value: Any) -> Any:
        if self.name == "string": return str(value)
        elif self.name == "int": return int(value)
        elif self.name == "float": return float(value)
        else: raise ValueError(f"Invalid type {self.name}")
    
    @property
    def content_type(self): 
        if self.name == "string": return "text"
        elif self.name == "int" or self.name == "float": return "number"
        else: raise ValueError(f"Invalid type {self.name}")

def flatten_task_type(t: TaskType, base_index: tuple[int, ...]) -> list[tuple[Literal["string", "int", "float"], tuple[int, ...]]]:
    if type(t) == tuple:
        return list(itertools.chain.from_iterable([ flatten_task_type(it, (*base_index, idx)) for idx, it in enumerate(t) ]))
    else:
        return [ (FunctionTaskType(t), base_index) ]

class FunctionTaskInfo:
    fn: callable
    name: str
    output_type: TaskType
    input_types: dict[str, TaskType]
    input_args_type: Optional[TaskType] = None
    
    config_model: Optional[type[BaseModel]] = None
    default_config: Optional[BaseModel] = None

    def __init__(
            self, 
            fn: callable):
        
        sig = inspect.signature(fn)
        
        self.fn = fn
        self.name = fn.__name__
        
        # output type
        self.output_type = get_signature_type(sig.return_annotation)
        
        # config model
        config_param = sig.parameters.get("config", None)
        if config_param is not None:
            if not issubclass(config_param.annotation, BaseModel): 
                raise ValueError(f"Invalid config model {config_param}. Must be a subclass of pydantic.BaseModel")
            else:
                self.config_model = config_param.annotation
            
            if config_param.default is not inspect.Parameter.empty and isinstance(config_param.default, BaseModel):
                self.default_config = config_param.default

        # input types
        self.input_types = { k: get_signature_type(v.annotation) for k, v in sig.parameters.items() if k != "config" and v.kind != inspect.Parameter.VAR_POSITIONAL }

        # input args type
        args_param = sig.parameters.get("args", None)
        if args_param is not None and args_param.kind == inspect.Parameter.VAR_POSITIONAL:
            self.input_args_type = get_signature_type(args_param.annotation)
    
    @property
    def pretty_name(self):
        name = self.name.replace("_", " ")
        name = "".join([ " " + c.lower() if c.isupper() else c for c in name ]).strip()
        return name.title()
    
    @property
    def flat_input_types(self): return { k: flatten_task_type(t, ()) for k, t in self.input_types.items() }
    @property
    def flat_input_args_type(self): return flatten_task_type(self.input_args_type, ())
    @property
    def flat_output_type(self): return flatten_task_type(self.output_type, ())
    
    def create_args_stream_group(self):
        if self.input_args_type is None: return None
        types = self.flat_input_args_type
        if len(types) == 0: return None
        
        return TaskStreamGroup(
            inputs=[
                TaskInputStream(
                    label=f"args {':'.join(index)}",
                    content_type=input_type.content_type
                ) for input_type, index in types   
            ],
            outputs=[]
        )
            
    
class FunctionTask(Task):
    def __init__(self, client: Client, info: FunctionTaskInfo, deployment: DeploymentTask):
        super().__init__(client)
        self.info = info
        self.deployment = deployment
    
    
    
class FunctionTaskFacotry(TaskFactoryWorker):
    def __init__(self, node_connection: Connection, info: FunctionTaskInfo):
        super().__init__(node_connection)
        self.info = info
    
    async def create_task(self, deployment: DeploymentTask) -> Task: return FunctionTask(await self.create_client(), self.info, deployment)
    async def rpc_connect(self, req: RPCTaskConnectRequest) -> DeploymentTask | None:
        # connect if types match
        for stream_group in req.task.stream_groups:
            for stream in stream_group.inputs:
                if stream.ref_id == req.input_id:
                    if req.output_stream is None:
                        stream.topic_id = None
                    elif stream.content_type == req.output_stream.content_type:
                        stream.topic_id = req.output_stream.topic_id
                    else:
                        raise Exception(f"Input stream type {stream.content_type} does not match task output type {self.info.output_type}")
                    break

        expand_args = self.info.input_args_type is not None and req.input_id in (stream.ref_id for stream in req.task.stream_groups[-1].inputs)
        if expand_args:
            req.task.stream_groups.append(self.info.create_args_stream_group())
    
    @property
    def task_template(self) -> DeploymentTask:
        return DeploymentTask(
            task_factory_id=self.id,
            config={
                "label": self.label,
                "hostname": self.hostname,
                "config": self.info.default_config.model_dump() if self.info.default_config is not None else {}
            },
            stream_groups= []
        )
    
    
            
            
    
    
# class GeneratedTask(Task):
#     def __init__(self, client: Client, fn: callable, deployment: DeploymentTask):
#         super().__init__(client)
#         self.fn = fn
#         self.deployment = deployment
        
#     async def start_task(self):
        
        

# class TaskFactoryBuilder:
#     def __init__(self) -> None:
#         self.name = None
    
#     @property
#     def name(self): return self._name
#     @name.setter
#     def name(self, value): self._name = value
    
#     @property
#     def factory(self):
#         return self._factory
    
    
class TestConfig(BaseModel):
    name: str
    value: int = 0
    
def test_dec(fn):
    info = FunctionTaskInfo(fn)
    print(info.pretty_name)
    print(info.flat_input_types)
    print(info.flat_input_args_type)
    print(info.flat_output_type)
    print(info)
    return fn

@test_dec
def test_task(value: float, config: TestConfig, *args: tuple[int, str]) -> float:
    return value + 1