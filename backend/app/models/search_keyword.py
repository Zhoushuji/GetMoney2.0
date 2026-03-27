import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, JSON, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SearchKeyword(Base):
    __tablename__ = "search_keywords"
    __table_args__ = (
        UniqueConstraint("keyword_normalized", "scope_fingerprint", name="uq_search_keywords_normalized_scope"),
        Index("ix_search_keywords_next_refresh_at", "next_refresh_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    keyword_normalized: Mapped[str] = mapped_column(String(500), nullable=False)
    scope_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    countries: Mapped[list | None] = mapped_column(JSON, nullable=True)
    languages: Mapped[list | None] = mapped_column(JSON, nullable=True)
    query_frontier: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    refresh_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    refresh_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    company_links = relationship(
        "SearchKeywordCompany",
        back_populates="search_keyword",
        cascade="all, delete-orphan",
    )
