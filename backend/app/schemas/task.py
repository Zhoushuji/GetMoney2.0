from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TaskCreateResponse(BaseModel):
    task_id: UUID


class TaskStatusResponse(BaseModel):
    id: UUID
    status: str
    progress: int
    total: int
    completed: int
    confirmed_leads: int
    target_count: int | None = None
    stopped_early: bool = False
    estimated_remaining_seconds: int | None = None
    results_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
