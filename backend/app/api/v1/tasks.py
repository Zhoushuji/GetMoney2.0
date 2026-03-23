from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.v1.leads import TASKS
from app.schemas.task import TaskStatusResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: UUID) -> TaskStatusResponse:
    task = TASKS.get(str(task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusResponse(**task, results_url=f"/api/v1/leads?task_id={task_id}")
