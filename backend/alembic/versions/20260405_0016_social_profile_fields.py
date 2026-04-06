"""add instagram and tiktok result fields

Revision ID: 20260405_0016
Revises: 20260405_0015
Create Date: 2026-04-06 09:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260405_0016"
down_revision = "20260405_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("instagram_url", sa.String(length=1000), nullable=True))
    op.add_column("companies", sa.Column("tiktok_url", sa.String(length=1000), nullable=True))
    op.add_column("leads", sa.Column("instagram_url", sa.String(length=1000), nullable=True))
    op.add_column("leads", sa.Column("tiktok_url", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "tiktok_url")
    op.drop_column("leads", "instagram_url")
    op.drop_column("companies", "tiktok_url")
    op.drop_column("companies", "instagram_url")
