"""user username normalized

Revision ID: 20260401_0009
Revises: 20260401_0007
Create Date: 2026-04-01 00:30:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260401_0009"
down_revision = "20260401_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    duplicates = connection.execute(
        sa.text(
            """
            select lower(btrim(username)) as username_normalized,
                   string_agg(username, ', ' order by username) as usernames
            from users
            group by lower(btrim(username))
            having count(*) > 1
            """
        )
    ).fetchall()
    if duplicates:
        duplicate_messages = [f"{row.username_normalized}: {row.usernames}" for row in duplicates]
        raise RuntimeError(
            "Cannot migrate users.username_normalized because case-insensitive username conflicts exist: "
            + "; ".join(duplicate_messages)
        )

    op.add_column("users", sa.Column("username_normalized", sa.String(length=100), nullable=True))
    connection.execute(sa.text("update users set username_normalized = lower(btrim(username)) where username_normalized is null"))
    op.alter_column("users", "username_normalized", existing_type=sa.String(length=100), nullable=False)
    op.create_unique_constraint("uq_users_username_normalized", "users", ["username_normalized"])


def downgrade() -> None:
    op.drop_constraint("uq_users_username_normalized", "users", type_="unique")
    op.drop_column("users", "username_normalized")
