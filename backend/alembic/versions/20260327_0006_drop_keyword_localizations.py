"""drop keyword localizations

Revision ID: 20260327_0006
Revises: 20260327_0005
Create Date: 2026-03-27 21:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260327_0006"
down_revision = "20260327_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("keyword_localizations")


def downgrade() -> None:
    op.create_table(
        "keyword_localizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("keyword_normalized", sa.String(length=500), nullable=False),
        sa.Column("country_code", sa.String(length=16), nullable=False),
        sa.Column("language_code", sa.String(length=16), nullable=False),
        sa.Column("localized_keyword", sa.String(length=500), nullable=False),
        sa.Column("positive_terms", sa.JSON(), nullable=True),
        sa.Column("negative_terms", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "keyword_normalized",
            "country_code",
            "language_code",
            "strategy_version",
            name="uq_keyword_localizations_scope",
        ),
    )
