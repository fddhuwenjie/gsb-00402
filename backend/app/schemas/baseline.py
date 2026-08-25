from pydantic import BaseModel, Field
from datetime import datetime


class BaselineCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    task_id: int = Field(..., gt=0)


class DiffGenerateRequest(BaseModel):
    task_id: int = Field(..., gt=0)


class BaselineDTO(BaseModel):
    id: int
    name: str
    task_id: int
    task_name: str = ""
    language: str
    code_path: str
    asset_count: int
    created_by: int
    creator_name: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class BaselineDetailDTO(BaseModel):
    baseline: BaselineDTO
    assets: list[dict]


class DiffReportDTO(BaseModel):
    id: int
    baseline_id: int
    baseline_name: str = ""
    task_id: int
    task_name: str = ""
    added_count: int
    removed_count: int
    changed_count: int
    created_by: int
    creator_name: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class DiffReportDetailDTO(BaseModel):
    report: DiffReportDTO
    diff: dict
