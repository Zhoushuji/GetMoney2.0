"""keyword frontier columns

Revision ID: 20260327_0004
Revises: 20260327_0003
Create Date: 2026-03-27 00:30:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260327_0004"
down_revision = "20260327_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("search_keywords", sa.Column("query_frontier", sa.JSON(), nullable=True))
    op.add_column(
        "search_keywords",
        sa.Column("last_requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_column("search_keywords", "last_requested_at")
    op.drop_column("search_keywords", "query_frontier")
