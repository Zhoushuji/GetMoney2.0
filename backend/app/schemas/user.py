from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class UserRead(BaseModel):
    id: UUID
    username: str
    role: str
    is_active: bool
    daily_task_limit: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    items: list[UserRead] = Field(default_factory=list)
    total: int = 0


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=8)
    role: Literal["admin", "user"] = "user"
    is_active: bool = True
    daily_task_limit: int = Field(default=3, ge=1, le=1000)


class UserUpdateRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1)
    role: Literal["admin", "user"] | None = None
    is_active: bool | None = None
    daily_task_limit: int | None = Field(default=None, ge=1, le=1000)


class UserPasswordUpdateRequest(BaseModel):
    password: str = Field(min_length=8)
