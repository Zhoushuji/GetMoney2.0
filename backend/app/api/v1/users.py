from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreateRequest,
    UserListResponse,
    UserPasswordUpdateRequest,
    UserRead,
    UserUpdateRequest,
)
from app.services.auth import hash_password, normalize_username

router = APIRouter(prefix="/users", tags=["users"])


async def _get_user_or_404(db: AsyncSession, user_id: UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("", response_model=UserListResponse)
async def list_users(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    total = int((await db.execute(select(func.count(User.id)))).scalar_one() or 0)
    result = await db.execute(select(User).order_by(User.created_at.asc(), User.username.asc()))
    items = [UserRead.model_validate(user) for user in result.scalars().all()]
    return UserListResponse(items=items, total=total)


@router.post("", response_model=UserRead)
async def create_user(
    payload: UserCreateRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    username = payload.username.strip()
    username_normalized = normalize_username(username)
    result = await db.execute(select(User).where(User.username_normalized == username_normalized))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=username,
        username_normalized=username_normalized,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
        daily_task_limit=payload.daily_task_limit,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    user = await _get_user_or_404(db, user_id)
    if payload.username is not None:
        username = payload.username.strip()
        username_normalized = normalize_username(username)
        result = await db.execute(select(User).where(User.username_normalized == username_normalized, User.id != user.id))
        if result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=400, detail="Username already exists")
        user.username = username
        user.username_normalized = username_normalized
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.daily_task_limit is not None:
        user.daily_task_limit = payload.daily_task_limit
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.patch("/{user_id}/password", response_model=UserRead)
async def reset_user_password(
    user_id: UUID,
    payload: UserPasswordUpdateRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    user = await _get_user_or_404(db, user_id)
    user.password_hash = hash_password(payload.password)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)
