from pydantic import BaseModel, Field
from datetime import datetime


class SignatureFileDTO(BaseModel):
    id: int
    name: str
    original_filename: str
    description: str
    rule_count: int
    function_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SignatureUploadRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=1000)


class SignatureContentDTO(BaseModel):
    id: int
    name: str
    original_filename: str
    description: str
    rule_count: int
    function_count: int
    rules: list[dict]
    created_at: datetime

    class Config:
        from_attributes = True
