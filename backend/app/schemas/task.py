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
    results_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
