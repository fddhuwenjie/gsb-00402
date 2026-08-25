from pydantic import BaseModel, Field
from datetime import datetime


class AnalysisCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    language: str = Field(..., min_length=1, max_length=20)
    code_path: str = Field(..., min_length=1, max_length=500)
    project_key: str | None = Field(default=None, max_length=200)
    signature_file_ids: list[int] = Field(..., min_length=1)
    baseline_id: int | None = Field(default=None, gt=0)


class AnalysisTaskDTO(BaseModel):
    id: int
    name: str
    language: str
    code_path: str
    project_key: str = ""
    status: str
    error_message: str | None
    created_by: int
    creator_name: str = ""
    signature_file_names: list[str] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AnalysisResultDTO(BaseModel):
    id: int
    task_id: int
    total_files_scanned: int
    total_matches: int
    total_components: int
    risk_level: str
    scan_duration: float
    report: dict
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisDetailDTO(BaseModel):
    task: AnalysisTaskDTO
    result: AnalysisResultDTO | None
