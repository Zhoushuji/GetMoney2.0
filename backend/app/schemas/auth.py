from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class CurrentUserResponse(BaseModel):
    id: UUID
    username: str
    role: str
    is_active: bool
    daily_task_limit: int
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: CurrentUserResponse
