"""add volcengine translation provider

Revision ID: 20260405_0013
Revises: 20260405_0012
Create Date: 2026-04-05 23:25:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260405_0013"
down_revision = "20260405_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("search_settings", sa.Column("volcengine_api_key", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("search_settings", "volcengine_api_key")
