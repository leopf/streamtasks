from pydantic import BaseModel
from typing import Optional, Any, Union
import itertools

class DashboardInfo(BaseModel):
  label: str
  id: str
  address: int

  @property
  def web_init_descriptor(self) -> str: return f"task_factory_{self.id}_web"

class DashboardDeleteMessage(BaseModel):
  id: str

class TaskFactoryInfo(BaseModel):
  id: str
  path: str

class TaskFactoryRegistration(BaseModel):
  id: str
  worker_address: int

  @property
  def web_init_descriptor(self) -> str: return f"task_factory_{self.id}_web"

class TaskFactoryDeleteMessage(BaseModel):
  id: str

class TaskStreamFormat(BaseModel):
  label: str
  content_type: Optional[str]
  encoding: Optional[str]

class TaskStream(TaskStreamFormat):
  topic_id: str

class TaskStreamFormatGroup(BaseModel):
  label: Optional[str]
  inputs: list[TaskStreamFormat]
  outputs: list[TaskStreamFormat]

class TaskStreamGroup(BaseModel):
  label: Optional[str]
  inputs: list[TaskStream]
  outputs: list[TaskStream]

class TaskFormat(BaseModel):
  task_factory_id: str
  label: str
  hostname: str
  stream_groups: list[TaskStreamFormatGroup]

class TaskDeploymentBase(BaseModel):
  task_factory_id: str
  label: str
  config: dict[str, Any]
  stream_groups: list[TaskStreamGroup]

  def get_topic_ids(self) -> set[str]:
    for stream_group in self.stream_groups:
      for stream in itertools.chain(stream_group.inputs, stream_group.outputs):
        yield stream.topic_id

class TaskDeployment(TaskDeploymentBase):
  id: str
  topic_id_map: dict[str, int]

class TaskDeploymentStatus(BaseModel):
  running: bool
  error: Optional[str]

  def validate_running(self, running: bool):
    if self.error is not None: raise Exception(f"task errored: {self.error}")
    if running and not self.running: raise Exception("task not running")
    if not running and self.running: raise Exception("task running but should not be")

class TaskDeploymentDeleteMessage(BaseModel):
  id: str

class Deployment(BaseModel):
  id: str
  tasks: list[TaskDeployment]
  status: str 

class TaskFetchDescriptors:
  REGISTER_TASK_FACTORY = "register_task_factory"
  UNREGISTER_TASK_FACTORY = "unregister_task_factory"
  DEPLOY_TASK = "deploy_task"
  DELETE_TASK = "delete_task"
  REGISTER_DASHBOARD = "register_dashboard"
  UNREGISTER_DASHBOARD = "unregister_dashboard"
