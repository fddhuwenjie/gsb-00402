from pydantic import BaseModel, Field
from datetime import datetime


class BaselineCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=1000)
    task_id: int = Field(..., gt=0)


class BaselineDTO(BaseModel):
    id: int
    name: str
    description: str
    source_task_id: int | None
    source_task_name: str = ""
    language: str
    code_path: str
    project_key: str = ""
    asset_count: int
    created_by: int
    creator_name: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class BaselineDetailDTO(BaselineDTO):
    report: dict


class DiffReportDTO(BaseModel):
    id: int
    baseline_id: int
    baseline_name: str = ""
    task_id: int
    task_name: str = ""
    added_count: int
    removed_count: int
    changed_count: int
    unchanged_count: int
    risk_level: str
    created_by: int
    creator_name: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class DiffDetailDTO(DiffReportDTO):
    diff: dict


class DiffCreateRequest(BaseModel):
    baseline_id: int = Field(..., gt=0)
    task_id: int = Field(..., gt=0)
