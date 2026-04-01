from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.lead import Lead
from app.models.task import Task
from app.models.user import User
from app.services.auth import AuthError, decode_access_token
from app.services.workspace_store import get_root_task

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(str(payload["sub"]))
    except (AuthError, KeyError, ValueError):
        raise _unauthorized("Invalid access token")
    user = await db.get(User, user_id)
    if user is None:
        raise _unauthorized("User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def task_visible_to_user(task: Task | None, current_user: User) -> bool:
    if task is None:
        return False
    if current_user.role == "admin":
        return True
    return task.user_id == current_user.id


async def ensure_task_access(session: AsyncSession, task_id: UUID, current_user: User) -> Task:
    task = await session.get(Task, task_id, options=[selectinload(Task.user)])
    if not task_visible_to_user(task, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


async def ensure_root_task_access(session: AsyncSession, task_id: UUID, current_user: User) -> Task:
    task = await get_root_task(session, task_id)
    if not task_visible_to_user(task, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


async def ensure_lead_access(
    session: AsyncSession,
    lead_id: UUID,
    current_user: User,
    *,
    with_contacts: bool = False,
) -> Lead:
    query = select(Lead).join(Task, Task.id == Lead.task_id).where(Lead.id == lead_id)
    if with_contacts:
        query = query.options(selectinload(Lead.contacts))
    if current_user.role != "admin":
        query = query.where(Task.user_id == current_user.id)
    result = await session.execute(query)
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


def start_of_today_utc() -> datetime:
    local_now = datetime.now().astimezone()
    local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return local_start.astimezone(timezone.utc)
