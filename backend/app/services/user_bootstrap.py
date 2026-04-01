from __future__ import annotations

from sqlalchemy import select, update

from app.config import get_settings
from app.database import SessionLocal
from app.models.task import Task
from app.models.user import User
from app.services.auth import hash_password, normalize_username


async def ensure_initial_admin() -> None:
    settings = get_settings()
    normalized_username = normalize_username(settings.initial_admin_username)
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.username_normalized == normalized_username)
        )
        admin = result.scalar_one_or_none()
        if admin is None:
            admin = User(
                username=settings.initial_admin_username,
                username_normalized=normalized_username,
                password_hash=hash_password(settings.initial_admin_password),
                role="admin",
                is_active=True,
                daily_task_limit=9999,
            )
            session.add(admin)
            await session.flush()
        else:
            admin.username = settings.initial_admin_username
            admin.username_normalized = normalized_username
            admin.role = "admin"
            admin.is_active = True
            if admin.daily_task_limit < 9999:
                admin.daily_task_limit = 9999

        await session.execute(
            update(Task)
            .where(Task.user_id.is_(None))
            .values(user_id=admin.id)
        )
        await session.commit()
