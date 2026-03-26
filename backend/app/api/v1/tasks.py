import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.task import TaskDetailResponse, TaskHistoryListResponse, TaskStatusResponse
from app.services.workspace_store import ROOT_TASK_TYPE, get_task, get_task_detail, get_task_history, task_to_status

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=TaskHistoryListResponse)
async def list_tasks(
    type: str = Query(ROOT_TASK_TYPE),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> TaskHistoryListResponse:
    return await get_task_history(db, limit=limit, offset=offset, task_type=type)


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task_detail_route(task_id: UUID, db: AsyncSession = Depends(get_db)) -> TaskDetailResponse:
    detail = await get_task_detail(db, task_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return detail


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: UUID, db: AsyncSession = Depends(get_db)) -> TaskStatusResponse:
    task = await get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_to_status(task)


@router.get("/{task_id}/stream")
async def stream_task_status(task_id: UUID, db: AsyncSession = Depends(get_db)):
    if not await get_task(db, task_id):
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_stream():
        while True:
            done = False
            async for payload, is_final in _yield_task_payload(task_id):
                yield payload
                done = is_final
            if done:
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _yield_task_payload(task_id: UUID):
    from app.database import SessionLocal

    async with SessionLocal() as session:
        task = await get_task(session, task_id)
        if not task:
            return
        payload = task_to_status(task)
        yield f"data: {payload.model_dump_json()}\n\n", payload.status in {"completed", "failed", "stopped_early"}
