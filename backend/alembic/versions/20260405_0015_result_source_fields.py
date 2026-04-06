"""add source fields for companies and leads

Revision ID: 20260405_0015
Revises: 20260405_0014
Create Date: 2026-04-06 00:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260405_0015"
down_revision = "20260405_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("source_url", sa.String(length=1000), nullable=True))
    op.add_column("companies", sa.Column("source_type", sa.String(length=50), nullable=True))
    op.create_unique_constraint("uq_companies_source_url", "companies", ["source_url"])

    op.add_column("leads", sa.Column("source_url", sa.String(length=1000), nullable=True))
    op.add_column("leads", sa.Column("source_type", sa.String(length=50), nullable=True))
    op.create_unique_constraint("uq_leads_task_source_url", "leads", ["task_id", "source_url"])


def downgrade() -> None:
    op.drop_constraint("uq_leads_task_source_url", "leads", type_="unique")
    op.drop_column("leads", "source_type")
    op.drop_column("leads", "source_url")

    op.drop_constraint("uq_companies_source_url", "companies", type_="unique")
    op.drop_column("companies", "source_type")
    op.drop_column("companies", "source_url")
