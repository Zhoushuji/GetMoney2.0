"""multi keyword cache

Revision ID: 20260327_0003
Revises: 20260326_0002
Create Date: 2026-03-27 00:00:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.services.search.keyword_cache import canonical_domain, next_refresh_at, normalize_keywords, scope_fingerprint

revision = "20260327_0003"
down_revision = "20260326_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("canonical_domain", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=500), nullable=True),
        sa.Column("website", sa.String(length=1000), nullable=True),
        sa.Column("facebook_url", sa.String(length=1000), nullable=True),
        sa.Column("linkedin_url", sa.String(length=1000), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("continent", sa.String(length=100), nullable=True),
        sa.Column("raw_profile", sa.JSON(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("canonical_domain", name="uq_companies_canonical_domain"),
    )
    op.create_table(
        "search_keywords",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("keyword", sa.String(length=500), nullable=False),
        sa.Column("keyword_normalized", sa.String(length=500), nullable=False),
        sa.Column("scope_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("countries", sa.JSON(), nullable=True),
        sa.Column("languages", sa.JSON(), nullable=True),
        sa.Column("query_frontier", sa.JSON(), nullable=True),
        sa.Column("refresh_status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("refresh_error", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("keyword_normalized", "scope_fingerprint", name="uq_search_keywords_normalized_scope"),
    )
    op.create_index("ix_search_keywords_next_refresh_at", "search_keywords", ["next_refresh_at"], unique=False)
    op.create_table(
        "search_keyword_companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("search_keyword_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("search_keywords.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_query", sa.String(length=1000), nullable=True),
        sa.Column("source_rank", sa.Integer(), nullable=True),
        sa.Column("source_title", sa.String(length=1000), nullable=True),
        sa.Column("source_snippet", sa.String(length=4000), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("search_keyword_id", "company_id", name="uq_search_keyword_companies_keyword_company"),
    )
    op.add_column("leads", sa.Column("matched_keywords", sa.JSON(), nullable=True))

    bind = op.get_bind()
    metadata = sa.MetaData()
    tasks = sa.Table("tasks", metadata, autoload_with=bind)
    leads = sa.Table("leads", metadata, autoload_with=bind)
    companies = sa.Table("companies", metadata, autoload_with=bind)
    search_keywords = sa.Table("search_keywords", metadata, autoload_with=bind)
    search_keyword_companies = sa.Table("search_keyword_companies", metadata, autoload_with=bind)

    task_rows = {
        row.id: row
        for row in bind.execute(
            sa.select(tasks.c.id, tasks.c.type, tasks.c.params, tasks.c.created_at, tasks.c.target_count)
        ).mappings()
    }

    task_keywords: dict[uuid.UUID, list[str]] = {}
    search_keyword_ids: dict[tuple[str, str], uuid.UUID] = {}
    company_ids: dict[str, uuid.UUID] = {}
    association_keys: set[tuple[uuid.UUID, uuid.UUID]] = set()

    for task_id, row in task_rows.items():
        params = dict(row.params or {})
        keywords = normalize_keywords(list(params.get("keywords") or []) + ([params["product_name"]] if params.get("product_name") else []))
        if not keywords:
            continue
        task_keywords[task_id] = keywords
        params["keywords"] = keywords
        params["product_name"] = keywords[0]
        bind.execute(
            tasks.update().where(tasks.c.id == task_id).values(params=params)
        )

    lead_rows = bind.execute(
        sa.select(
            leads.c.id,
            leads.c.task_id,
            leads.c.company_name,
            leads.c.website,
            leads.c.facebook_url,
            leads.c.linkedin_url,
            leads.c.country,
            leads.c.continent,
            leads.c.source,
            leads.c.raw_data,
            leads.c.created_at,
        )
    ).mappings()

    for lead_row in lead_rows:
        keywords = task_keywords.get(lead_row.task_id) or []
        if not keywords:
            continue
        matched_keywords = keywords[:1]
        raw_data = dict(lead_row.raw_data or {})
        raw_data.setdefault("matched_keywords", matched_keywords)
        bind.execute(
            leads.update()
            .where(leads.c.id == lead_row.id)
            .values(matched_keywords=matched_keywords, raw_data=raw_data)
        )

        task_row = task_rows.get(lead_row.task_id)
        params = dict((task_row.params or {}) if task_row is not None else {})
        countries = list(params.get("countries") or [])
        languages = list(params.get("languages") or [])

        domain = canonical_domain(lead_row.website)
        if not domain:
            continue

        company_id = company_ids.get(domain)
        if company_id is None:
            company_id = uuid.uuid4()
            company_ids[domain] = company_id
            bind.execute(
                companies.insert().values(
                    id=company_id,
                    canonical_domain=domain,
                    company_name=lead_row.company_name,
                    website=lead_row.website,
                    facebook_url=lead_row.facebook_url,
                    linkedin_url=lead_row.linkedin_url,
                    country=lead_row.country,
                    continent=lead_row.continent,
                    raw_profile=raw_data,
                    first_seen_at=lead_row.created_at,
                    last_seen_at=lead_row.created_at,
                    last_refreshed_at=lead_row.created_at,
                )
            )

        for keyword in matched_keywords:
            keyword_norm = keyword.lower()
            fingerprint = scope_fingerprint(countries=countries, languages=languages)
            keyword_key = (keyword_norm, fingerprint)
            search_keyword_id = search_keyword_ids.get(keyword_key)
            if search_keyword_id is None:
                search_keyword_id = uuid.uuid4()
                search_keyword_ids[keyword_key] = search_keyword_id
                created_at = task_row.created_at if task_row is not None else lead_row.created_at
                bind.execute(
                    search_keywords.insert().values(
                        id=search_keyword_id,
                        keyword=keyword,
                        keyword_normalized=keyword_norm,
                        scope_fingerprint=fingerprint,
                        countries=countries,
                        languages=languages,
                        query_frontier={},
                        refresh_status="completed",
                        refresh_error=None,
                        created_at=created_at,
                        last_requested_at=created_at,
                        last_refreshed_at=created_at,
                        next_refresh_at=next_refresh_at(created_at),
                    )
                )

            association_key = (search_keyword_id, company_id)
            if association_key in association_keys:
                continue
            association_keys.add(association_key)
            bind.execute(
                search_keyword_companies.insert().values(
                    id=uuid.uuid4(),
                    search_keyword_id=search_keyword_id,
                    company_id=company_id,
                    source_query=None,
                    source_rank=None,
                    source_title=raw_data.get("search_title"),
                    source_snippet=raw_data.get("search_snippet"),
                    first_seen_at=lead_row.created_at,
                    last_seen_at=lead_row.created_at,
                )
            )


def downgrade() -> None:
    op.drop_column("leads", "matched_keywords")
    op.drop_table("search_keyword_companies")
    op.drop_index("ix_search_keywords_next_refresh_at", table_name="search_keywords")
    op.drop_table("search_keywords")
    op.drop_table("companies")
