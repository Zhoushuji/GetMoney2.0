import asyncio
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_root_task_access, ensure_task_access, get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.task import TaskDetailResponse, TaskHistoryListResponse, TaskStatusResponse
from app.services.workspace_store import ROOT_TASK_TYPE, get_task, get_task_detail, get_task_history, task_to_status

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=TaskHistoryListResponse)
async def list_tasks(
    type: str = Query(ROOT_TASK_TYPE),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    all_users: bool = Query(False),
    user_id: UUID | None = Query(None),
    owner_role: str | None = Query(None),
    status: str | None = Query(None),
    created_from: datetime | None = Query(None),
    created_to: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskHistoryListResponse:
    if current_user.role == "admin" and all_users:
        owner_filter = user_id
        role_filter = owner_role
    else:
        owner_filter = current_user.id
        role_filter = None
    return await get_task_history(
        db,
        limit=limit,
        offset=offset,
        task_type=type,
        user_id=owner_filter,
        owner_role=role_filter,
        status=status,
        created_from=created_from,
        created_to=created_to,
    )


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task_detail_route(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskDetailResponse:
    await ensure_root_task_access(db, task_id, current_user)
    detail = await get_task_detail(db, task_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return detail


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskStatusResponse:
    task = await ensure_task_access(db, task_id, current_user)
    return task_to_status(task)


@router.get("/{task_id}/stream")
async def stream_task_status(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await ensure_task_access(db, task_id, current_user)

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


@router.delete("/{task_id}")
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> dict:
    task = await ensure_task_access(db, task_id, current_admin)
    if task.parent_task_id is not None or task.type != ROOT_TASK_TYPE:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()
    return {"deleted": True}
