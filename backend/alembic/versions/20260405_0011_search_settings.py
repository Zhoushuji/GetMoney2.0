"""search settings

Revision ID: 20260405_0011
Revises: 20260405_0010
Create Date: 2026-04-05 08:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260405_0011"
down_revision = "20260405_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("openai_api_key", sa.String(length=500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("search_settings")
