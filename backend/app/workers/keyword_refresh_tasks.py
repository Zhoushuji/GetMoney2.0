import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.api.v1.leads import (
    SearchRuntime,
    _claim_keyword_refresh,
    _mark_keyword_refresh_failed,
    _refresh_keyword_cache,
)
from app.database import SessionLocal
from app.models.search_keyword import SearchKeyword
from app.schemas.lead import LeadSearchRequest
from app.workers.celery_app import celery_app


async def _load_due_search_keywords(limit: int) -> list[SearchKeyword]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(SearchKeyword)
            .where(
                SearchKeyword.next_refresh_at.is_not(None),
                SearchKeyword.next_refresh_at <= datetime.now(timezone.utc),
                SearchKeyword.refresh_status != "running",
            )
            .order_by(SearchKeyword.next_refresh_at.asc(), SearchKeyword.created_at.asc())
            .limit(limit)
        )
        return result.scalars().all()


async def _refresh_due_keywords(limit: int) -> dict[str, int]:
    runtime = SearchRuntime()
    refreshed = 0
    skipped = 0
    due_keywords = await _load_due_search_keywords(limit)
    for keyword_row in due_keywords:
        claimed = await _claim_keyword_refresh(keyword_row.id)
        if not claimed:
            skipped += 1
            continue
        try:
            payload = LeadSearchRequest(
                keywords=[keyword_row.keyword],
                product_name=keyword_row.keyword,
                continents=[],
                countries=list(keyword_row.countries or []),
                languages=list(keyword_row.languages or []),
                target_count=None,
                mode="live",
            )
            await _refresh_keyword_cache(
                runtime,
                search_keyword_id=keyword_row.id,
                child_task_id=None,
                keyword=keyword_row.keyword,
                payload=payload,
                target_count=None,
                refresh_one_round=True,
            )
            refreshed += 1
        except Exception as exc:
            await _mark_keyword_refresh_failed(keyword_row.id, exc)
    return {"refreshed": refreshed, "skipped": skipped}


@celery_app.task(name="workers.keyword_refresh_tasks.refresh_due_search_keywords")
def refresh_due_search_keywords(limit: int = 20) -> dict[str, int]:
    return asyncio.run(_refresh_due_keywords(limit))
