import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("task_id", "website", name="uq_leads_task_website"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"))
    company_name: Mapped[str | None] = mapped_column(String(500))
    website: Mapped[str | None] = mapped_column(String(1000))
    facebook_url: Mapped[str | None] = mapped_column(String(1000))
    linkedin_url: Mapped[str | None] = mapped_column(String(1000))
    country: Mapped[str | None] = mapped_column(String(100))
    continent: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str | None] = mapped_column(String(100))
    contact_status: Mapped[str] = mapped_column(String(50), default="pending")
    decision_maker_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    general_contact_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_title: Mapped[str | None] = mapped_column(String(500))
    linkedin_personal_url: Mapped[str | None] = mapped_column(String(1000))
    personal_email: Mapped[str | None] = mapped_column(String(255))
    work_email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    whatsapp: Mapped[str | None] = mapped_column(String(50))
    potential_contacts: Mapped[dict | None] = mapped_column(JSON)
    general_emails: Mapped[list | None] = mapped_column(JSON)
    raw_data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task = relationship("Task", back_populates="leads")
    contacts = relationship("Contact", back_populates="lead", cascade="all, delete-orphan")
