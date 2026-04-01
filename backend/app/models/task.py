import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confirmed_leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stopped_early: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    estimated_total_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_remaining_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phase: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    processed_search_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    planned_search_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_candidates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    planned_candidate_budget: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    parent_task = relationship("Task", remote_side=[id], back_populates="child_tasks")
    child_tasks = relationship("Task", back_populates="parent_task", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="task", cascade="all, delete-orphan")
    user = relationship("User", back_populates="tasks")
