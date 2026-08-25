from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field(default="user")


class UserUpdateRequest(BaseModel):
    role: str | None = None
    password: str | None = None
