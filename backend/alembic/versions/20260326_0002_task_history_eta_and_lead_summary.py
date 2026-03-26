"""task history eta and lead summary

Revision ID: 20260326_0002
Revises: 20260322_0001
Create Date: 2026-03-26 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260326_0002"
down_revision = "20260322_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("parent_task_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("tasks", sa.Column("completed", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tasks", sa.Column("stopped_early", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("tasks", sa.Column("error", sa.String(length=2000), nullable=True))
    op.add_column("tasks", sa.Column("estimated_total_seconds", sa.Integer(), nullable=True))
    op.add_column("tasks", sa.Column("estimated_remaining_seconds", sa.Integer(), nullable=True))
    op.add_column("tasks", sa.Column("phase", sa.String(length=50), nullable=False, server_default="queued"))
    op.add_column("tasks", sa.Column("processed_search_requests", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tasks", sa.Column("planned_search_requests", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tasks", sa.Column("processed_candidates", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tasks", sa.Column("planned_candidate_budget", sa.Integer(), nullable=False, server_default="0"))
    op.create_foreign_key("fk_tasks_parent_task", "tasks", "tasks", ["parent_task_id"], ["id"], ondelete="CASCADE")

    op.add_column("leads", sa.Column("decision_maker_status", sa.String(length=50), nullable=False, server_default="pending"))
    op.add_column("leads", sa.Column("general_contact_status", sa.String(length=50), nullable=False, server_default="pending"))
    op.add_column("leads", sa.Column("contact_name", sa.String(length=255), nullable=True))
    op.add_column("leads", sa.Column("contact_title", sa.String(length=500), nullable=True))
    op.add_column("leads", sa.Column("linkedin_personal_url", sa.String(length=1000), nullable=True))
    op.add_column("leads", sa.Column("personal_email", sa.String(length=255), nullable=True))
    op.add_column("leads", sa.Column("work_email", sa.String(length=255), nullable=True))
    op.add_column("leads", sa.Column("phone", sa.String(length=50), nullable=True))
    op.add_column("leads", sa.Column("whatsapp", sa.String(length=50), nullable=True))
    op.add_column("leads", sa.Column("potential_contacts", sa.JSON(), nullable=True))
    op.add_column("leads", sa.Column("general_emails", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "general_emails")
    op.drop_column("leads", "potential_contacts")
    op.drop_column("leads", "whatsapp")
    op.drop_column("leads", "phone")
    op.drop_column("leads", "work_email")
    op.drop_column("leads", "personal_email")
    op.drop_column("leads", "linkedin_personal_url")
    op.drop_column("leads", "contact_title")
    op.drop_column("leads", "contact_name")
    op.drop_column("leads", "general_contact_status")
    op.drop_column("leads", "decision_maker_status")

    op.drop_constraint("fk_tasks_parent_task", "tasks", type_="foreignkey")
    op.drop_column("tasks", "planned_candidate_budget")
    op.drop_column("tasks", "processed_candidates")
    op.drop_column("tasks", "planned_search_requests")
    op.drop_column("tasks", "processed_search_requests")
    op.drop_column("tasks", "phase")
    op.drop_column("tasks", "estimated_remaining_seconds")
    op.drop_column("tasks", "estimated_total_seconds")
    op.drop_column("tasks", "error")
    op.drop_column("tasks", "stopped_early")
    op.drop_column("tasks", "completed")
    op.drop_column("tasks", "parent_task_id")
