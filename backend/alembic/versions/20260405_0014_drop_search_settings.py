"""drop obsolete search settings table

Revision ID: 20260405_0014
Revises: 20260405_0013
Create Date: 2026-04-05 23:55:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260405_0014"
down_revision = "20260405_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("search_settings")


def downgrade() -> None:
    op.create_table(
        "search_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("active_translation_provider", sa.String(length=32), nullable=True),
        sa.Column("active_translation_model", sa.String(length=120), nullable=True),
        sa.Column("openai_api_key", sa.String(length=500), nullable=True),
        sa.Column("openrouter_api_key", sa.String(length=500), nullable=True),
        sa.Column("volcengine_api_key", sa.String(length=500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
