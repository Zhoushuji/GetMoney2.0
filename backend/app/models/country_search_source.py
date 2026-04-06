import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CountrySearchSource(Base):
    __tablename__ = "country_search_sources"
    __table_args__ = (
        UniqueConstraint("country_code", "source_type", "source_rank", name="uq_country_search_sources_rank"),
        Index("ix_country_search_sources_country_code", "country_code"),
        Index("ix_country_search_sources_domain", "source_domain"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_code: Mapped[str] = mapped_column(String(8), nullable=False)
    country_name: Mapped[str] = mapped_column(String(255), nullable=False)
    continent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    selection_mode: Mapped[str | None] = mapped_column(String(255), nullable=True)
    method_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
