from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TaskCreateResponse(BaseModel):
    task_id: UUID


class TaskStatusResponse(BaseModel):
    id: UUID
    type: str | None = None
    parent_task_id: UUID | None = None
    status: str
    progress: int
    total: int
    completed: int
    confirmed_leads: int
    target_count: int | None = None
    stopped_early: bool = False
    error: str | None = None
    estimated_total_seconds: int | None = None
    estimated_remaining_seconds: int | None = None
    phase: str | None = None
    processed_search_requests: int | None = None
    planned_search_requests: int | None = None
    processed_candidates: int | None = None
    planned_candidate_budget: int | None = None
    results_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskChildSummaryResponse(BaseModel):
    id: UUID
    type: str | None = None
    status: str
    progress: int
    confirmed_leads: int = 0
    mode: str | None = None
    keyword: str | None = None
    cache_hit: bool = False
    updated_at: datetime | None = None


class TaskSummaryResponse(TaskStatusResponse):
    params: dict | None = None
    keywords: list[str] = Field(default_factory=list)
    keyword_count: int = 0
    completed_keyword_count: int = 0
    cache_hit_keyword_count: int = 0
    keyword_tasks: list[TaskChildSummaryResponse] = Field(default_factory=list)
    lead_count: int = 0
    decision_maker_done_count: int = 0
    general_contact_done_count: int = 0
    latest_contact_task: TaskChildSummaryResponse | None = None


class TaskHistoryListResponse(BaseModel):
    items: list[TaskSummaryResponse]
    total: int
    limit: int
    offset: int


class TaskDetailResponse(TaskSummaryResponse):
    pass
