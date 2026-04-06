"""translation support

Revision ID: 20260405_0010
Revises: 20260401_0009
Create Date: 2026-04-05 00:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260405_0010"
down_revision = "20260401_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("daily_translation_limit", sa.Integer(), nullable=True))
    op.execute("update users set daily_translation_limit = 50 where daily_translation_limit is null")
    op.alter_column("users", "daily_translation_limit", existing_type=sa.Integer(), nullable=False)

    op.create_table(
        "keyword_translations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("keyword", sa.String(length=500), nullable=False),
        sa.Column("keyword_normalized", sa.String(length=500), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("source_language", sa.String(length=16), nullable=False),
        sa.Column("target_language", sa.String(length=16), nullable=False),
        sa.Column("translated_keyword", sa.String(length=500), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "keyword_normalized",
            "country_code",
            "source_language",
            "target_language",
            "strategy_version",
            name="uq_keyword_translations_lookup",
        ),
    )

    op.create_table(
        "translation_api_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("keyword", sa.String(length=500), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("source_language", sa.String(length=16), nullable=False),
        sa.Column("target_language", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("translation_api_requests")
    op.drop_table("keyword_translations")
    op.drop_column("users", "daily_translation_limit")
