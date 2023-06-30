from pydantic import BaseModel
from typing import Optional, Any

class DashboardInfo(BaseModel):
  label: str
  id: str
  address: int

  @property
  def web_init_descriptor(self) -> str: return f"task_factory_{self.id}_web"

class DashboardDeleteMessage(BaseModel):
  id: str

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
  placeholder: Optional[bool]
  inputs: list[TaskStreamFormat]
  outputs: list[TaskStreamFormat]

class TaskStreamGroup(BaseModel):
  label: Optional[str]
  placeholder: Optional[bool]
  inputs: list[TaskStream]
  outputs: list[TaskStream]

class TaskFormat(BaseModel):
  task_factory_id: str
  label: str
  hostname: str
  worker_id: str
  stream_groups: list[TaskStreamFormatGroup]

class TaskDeployment(BaseModel):
  id: str
  task_factory_id: str
  label: str
  config: Any
  stream_groups: list[TaskStreamGroup]
  topic_id_map: dict[str, int]

class TaskDeploymentDeleteMessage(BaseModel):
  id: str

class TaskFetchDescriptors:
  REGISTER_TASK_FACTORY = "register_task_factory"
  UNREGISTER_TASK_FACTORY = "unregister_task_factory"
  DEPLOY_TASK = "deploy_task"
  DELETE_TASK = "delete_task"
  REGISTER_DASHBOARD = "register_dashboard"
  UNREGISTER_DASHBOARD = "unregister_dashboard"
