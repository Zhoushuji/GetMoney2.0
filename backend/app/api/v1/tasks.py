import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.v1.leads import TASKS, build_task_status
from app.schemas.task import TaskStatusResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: UUID) -> TaskStatusResponse:
    task = TASKS.get(str(task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return build_task_status(task)


@router.get("/{task_id}/stream")
async def stream_task_status(task_id: UUID):
    task = TASKS.get(str(task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_stream():
        while True:
            payload = build_task_status(task)
            yield f"data: {payload.model_dump_json()}\n\n"
            if payload.status in {"completed", "failed", "stopped_early"}:
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
