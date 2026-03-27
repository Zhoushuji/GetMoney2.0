"""reviews and keyword localizations

Revision ID: 20260327_0005
Revises: 20260327_0004
Create Date: 2026-03-27 12:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260327_0005"
down_revision = "20260327_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_key", sa.String(length=100), nullable=False),
        sa.Column("verdict", sa.String(length=20), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("lead_id", "field_key", name="uq_lead_reviews_lead_field"),
    )
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


def downgrade() -> None:
    op.drop_table("keyword_localizations")
    op.drop_table("lead_reviews")
