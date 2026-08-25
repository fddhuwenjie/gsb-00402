from pydantic import BaseModel, Field
from datetime import datetime


class BaselineCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=1000)
    task_id: int


class BaselineDTO(BaseModel):
    id: int
    name: str
    description: str
    task_id: int
    task_name: str = ""
    language: str
    total_assets: int
    risk_level: str
    created_by: int
    creator_name: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class BaselineDetailDTO(BaselineDTO):
    assets: list[dict] = []
    source_summary: dict | None = None


class DiffCreateRequest(BaseModel):
    name: str = Field("", max_length=200)
    baseline_id: int
    task_id: int


class DiffReportDTO(BaseModel):
    id: int
    name: str
    baseline_id: int
    baseline_name: str = ""
    task_id: int
    task_name: str = ""
    added_count: int
    removed_count: int
    changed_count: int
    risk_level: str
    created_by: int
    creator_name: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class DiffReportDetailDTO(DiffReportDTO):
    diff: dict
