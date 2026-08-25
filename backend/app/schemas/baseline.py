from pydantic import BaseModel, Field
from datetime import datetime


class BaselineCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    task_id: int = Field(..., description="已完成分析任务的 ID，其报告将作为基线快照")


class DiffGenerateRequest(BaseModel):
    task_id: int = Field(..., description="用于与基线比较的已完成分析任务 ID")


class BaselineDTO(BaseModel):
    id: int
    name: str
    description: str
    task_id: int
    task_name: str = ""
    language: str
    code_path: str
    project_key: str
    created_by: int
    creator_name: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class DiffReportDTO(BaseModel):
    id: int
    baseline_id: int
    baseline_name: str = ""
    task_id: int
    task_name: str = ""
    total_added: int
    total_removed: int
    total_changed: int
    diff: dict
    created_by: int
    creator_name: str = ""
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DiffReportSummaryDTO(BaseModel):
    id: int
    baseline_id: int
    baseline_name: str = ""
    task_id: int
    task_name: str = ""
    total_added: int
    total_removed: int
    total_changed: int
    created_at: datetime

    class Config:
        from_attributes = True
