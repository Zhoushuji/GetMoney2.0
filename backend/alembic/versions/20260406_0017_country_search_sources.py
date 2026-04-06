"""create country search sources table

Revision ID: 20260406_0017
Revises: 20260405_0016
Create Date: 2026-04-06 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260406_0017"
down_revision: str | None = "20260405_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "country_search_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("country_name", sa.String(length=255), nullable=False),
        sa.Column("continent", sa.String(length=64), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_rank", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2000), nullable=False),
        sa.Column("source_domain", sa.String(length=255), nullable=False),
        sa.Column("selection_mode", sa.String(length=255), nullable=True),
        sa.Column("method_note", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("country_code", "source_type", "source_rank", name="uq_country_search_sources_rank"),
    )
    op.create_index("ix_country_search_sources_country_code", "country_search_sources", ["country_code"], unique=False)
    op.create_index("ix_country_search_sources_domain", "country_search_sources", ["source_domain"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_country_search_sources_domain", table_name="country_search_sources")
    op.drop_index("ix_country_search_sources_country_code", table_name="country_search_sources")
    op.drop_table("country_search_sources")
