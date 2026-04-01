import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.api.deps import task_visible_to_user
from app.api.v1.leads import _enforce_daily_task_limit
from app.models.task import Task
from app.models.user import User
from app.services.auth import create_access_token, decode_access_token, hash_password, normalize_username, verify_password


class _FakeResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _FakeSession:
    def __init__(self, count: int) -> None:
        self.count = count
        self.executed = []

    async def execute(self, statement):
        self.executed.append(statement)
        return _FakeResult(self.count)


def _user(*, role: str = "user", daily_task_limit: int = 3) -> User:
    username = f"{role}-{uuid.uuid4()}"
    return User(
        id=uuid.uuid4(),
        username=username,
        username_normalized=normalize_username(username),
        password_hash=hash_password("password-123"),
        role=role,
        is_active=True,
        daily_task_limit=daily_task_limit,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_password_hash_roundtrip() -> None:
    password_hash = hash_password("Maxwell0088..")

    assert verify_password("Maxwell0088..", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_normalize_username_is_case_insensitive_and_trimmed() -> None:
    assert normalize_username("  Haocheng  ") == "haocheng"
    assert normalize_username("MAX.User") == "max.user"


def test_access_token_roundtrip() -> None:
    user = _user(role="admin", daily_task_limit=9999)

    token = create_access_token(user)
    payload = decode_access_token(token)

    assert payload["sub"] == str(user.id)
    assert payload["username"] == user.username
    assert payload["role"] == "admin"


def test_task_visible_to_user_respects_owner() -> None:
    owner = _user()
    other = _user()
    admin = _user(role="admin")
    task = Task(
        id=uuid.uuid4(),
        user_id=owner.id,
        type="lead_search",
        status="completed",
        progress=100,
        total=1,
        completed=1,
        confirmed_leads=1,
    )

    assert task_visible_to_user(task, owner) is True
    assert task_visible_to_user(task, other) is False
    assert task_visible_to_user(task, admin) is True


def test_daily_task_limit_blocks_fourth_root_task_for_user() -> None:
    fake_db = _FakeSession(count=3)
    user = _user(daily_task_limit=3)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_enforce_daily_task_limit(fake_db, user))

    assert exc_info.value.status_code == 429
    assert "Daily root task limit reached" in exc_info.value.detail
    assert len(fake_db.executed) == 1


def test_daily_task_limit_does_not_block_admin() -> None:
    fake_db = _FakeSession(count=999)
    admin = _user(role="admin", daily_task_limit=1)

    asyncio.run(_enforce_daily_task_limit(fake_db, admin))

    assert fake_db.executed == []
