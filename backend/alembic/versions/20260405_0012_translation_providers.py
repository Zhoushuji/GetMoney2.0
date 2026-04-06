"""translation providers

Revision ID: 20260405_0012
Revises: 20260405_0011
Create Date: 2026-04-05 21:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260405_0012"
down_revision = "20260405_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("search_settings", sa.Column("active_translation_provider", sa.String(length=32), nullable=True))
    op.add_column("search_settings", sa.Column("active_translation_model", sa.String(length=120), nullable=True))
    op.add_column("search_settings", sa.Column("openrouter_api_key", sa.String(length=500), nullable=True))
    op.execute(
        """
        update search_settings
        set active_translation_provider = 'openai'
        where coalesce(trim(openai_api_key), '') <> ''
          and active_translation_provider is null
        """
    )
    op.execute(
        """
        update search_settings
        set active_translation_model = 'gpt-5.4-nano'
        where active_translation_provider = 'openai'
          and coalesce(trim(active_translation_model), '') = ''
        """
    )

    op.add_column("translation_api_requests", sa.Column("provider", sa.String(length=32), nullable=True))
    op.execute("update translation_api_requests set provider = 'openai' where provider is null")
    op.execute("update translation_api_requests set source_language = 'input' where source_language = 'en'")
    op.alter_column("translation_api_requests", "provider", nullable=False)

    op.execute("alter table keyword_translations drop constraint if exists uq_keyword_translations_lookup")
    op.execute("update keyword_translations set provider = 'openai' where provider is null or provider = 'openai_responses'")
    op.execute("update keyword_translations set source_language = 'input' where source_language = 'en'")
    op.create_unique_constraint(
        "uq_keyword_translations_lookup",
        "keyword_translations",
        ["keyword_normalized", "country_code", "source_language", "target_language", "provider", "model", "strategy_version"],
    )


def downgrade() -> None:
    op.execute("alter table keyword_translations drop constraint if exists uq_keyword_translations_lookup")
    op.execute("update keyword_translations set source_language = 'en' where source_language = 'input'")
    op.execute("update keyword_translations set provider = 'openai_responses' where provider = 'openai'")
    op.create_unique_constraint(
        "uq_keyword_translations_lookup",
        "keyword_translations",
        ["keyword_normalized", "country_code", "source_language", "target_language", "strategy_version"],
    )

    op.execute("update translation_api_requests set source_language = 'en' where source_language = 'input'")
    op.drop_column("translation_api_requests", "provider")

    op.drop_column("search_settings", "openrouter_api_key")
    op.drop_column("search_settings", "active_translation_model")
    op.drop_column("search_settings", "active_translation_provider")
