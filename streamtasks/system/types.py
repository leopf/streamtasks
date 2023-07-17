from pydantic import BaseModel, Field
from typing import Optional, Any, Literal
from uuid import uuid4
import itertools

def uuid4_str() -> str: return str(uuid4())

class DashboardRegistration(BaseModel):
  label: str
  id: str
  address: int

  @property
  def web_init_descriptor(self) -> str: return f"task_factory_{self.id}_web"

class DashboardDeleteMessage(BaseModel):
  id: str

class DashboardInfo(BaseModel):
  id: str
  path: str
  label: str

class TaskStreamBase(BaseModel):
  label: str
  content_type: Optional[str] = None
  encoding: Optional[str] = None
  extra: Optional[dict[str, Any]] = None

class TaskInputStream(TaskStreamBase):
  topic_id: Optional[str] = None
  ref_id: str = Field(default_factory=uuid4_str)

class TaskOutputStream(TaskStreamBase):
  topic_id: str = Field(default_factory=uuid4_str)

class TaskStreamGroup(BaseModel):
  inputs: list[TaskInputStream]
  outputs: list[TaskOutputStream]

class DeploymentTask(BaseModel):
  id: str = Field(default_factory=uuid4_str)
  task_factory_id: str
  config: dict[str, Any] = {}
  stream_groups: list[TaskStreamGroup]
  topic_id_map: dict[str, int] = {}

  def get_topic_ids(self) -> set[str]:
    for stream_group in self.stream_groups:
      for stream in itertools.chain(stream_group.inputs, stream_group.outputs):
        if stream.topic_id is not None:
          yield stream.topic_id

class TaskDeploymentStatus(BaseModel):
  running: bool
  error: Optional[str] = None

  def validate_running(self, running: bool):
    if self.error is not None: raise Exception(f"task errored: {self.error}")
    if running and not self.running: raise Exception("task not running")
    if not running and self.running: raise Exception("task running but should not be")

class TaskDeploymentDeleteMessage(BaseModel):
  id: str

class TaskFactoryRegistration(BaseModel):
  id: str
  worker_address: int
  task_template: DeploymentTask

  @property
  def web_init_descriptor(self) -> str: return f"task_factory_{self.id}_web"

class TaskFactoryDeleteMessage(BaseModel):
  id: str

DeploymentStatus = Literal["offline", "starting", "running", "stopping", "failing", "failed"]

class DeploymentBase(BaseModel):
  id: str = Field(default_factory=uuid4_str)
  label: str = "new deployment"
  status: DeploymentStatus = "offline"

class Deployment(DeploymentBase):
  tasks: list[DeploymentTask] = []

class DeploymentStatusInfo(BaseModel):
  status: DeploymentStatus
  started: bool

class RPCTaskConnectRequest(BaseModel):
  input_id: str
  output_stream: Optional[TaskOutputStream] = None
  task: DeploymentTask

class RPCTaskConnectResponse(BaseModel):
  task: Optional[DeploymentTask] = None
  error_message: Optional[str] = None

class SystemLogQueryParams(BaseModel):
  count: int = 100
  offset: int = 0

class SystemLogEntry(BaseModel):
  id: str = Field(default_factory=uuid4_str)
  message: str
  level: str
  timestamp: int

class TaskFetchDescriptors:
  REGISTER_TASK_FACTORY = "register_task_factory"
  UNREGISTER_TASK_FACTORY = "unregister_task_factory"
  DEPLOY_TASK = "deploy_task"
  DELETE_TASK = "delete_task"
  REGISTER_DASHBOARD = "register_dashboard"
  UNREGISTER_DASHBOARD = "unregister_dashboard"
