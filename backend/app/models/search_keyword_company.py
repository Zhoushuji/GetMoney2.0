import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SearchKeywordCompany(Base):
    __tablename__ = "search_keyword_companies"
    __table_args__ = (
        UniqueConstraint("search_keyword_id", "company_id", name="uq_search_keyword_companies_keyword_company"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_keyword_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("search_keywords.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    source_query: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_snippet: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    search_keyword = relationship("SearchKeyword", back_populates="company_links")
    company = relationship("Company", back_populates="keyword_links")


__all__ = ["SearchKeywordCompany"]
