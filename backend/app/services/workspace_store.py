from __future__ import annotations

from uuid import UUID

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.contact import Contact
from app.models.lead import Lead
from app.models.lead_review import LeadReview
from app.models.task import Task
from app.schemas.contact import ContactRead
from app.schemas.lead import LeadListResponse, LeadRead
from app.schemas.review import LeadReviewAnnotation
from app.schemas.task import (
    TaskChildSummaryResponse,
    TaskDetailResponse,
    TaskHistoryListResponse,
    TaskStatusResponse,
    TaskSummaryResponse,
)

ROOT_TASK_TYPE = "lead_search"
KEYWORD_TASK_TYPE = "lead_search_keyword"
CONTACT_TASK_TYPE = "contact_enrich"
MAX_ROOT_TASK_HISTORY = 20


def _effective_status(task: Task) -> str:
    if task.stopped_early and task.status == "completed":
        return "stopped_early"
    return task.status


def task_to_status(task: Task) -> TaskStatusResponse:
    return TaskStatusResponse(
        id=task.id,
        type=task.type,
        parent_task_id=task.parent_task_id,
        status=_effective_status(task),
        progress=task.progress,
        total=task.total,
        completed=task.completed,
        confirmed_leads=task.confirmed_leads,
        target_count=task.target_count,
        stopped_early=task.stopped_early,
        error=task.error,
        estimated_total_seconds=task.estimated_total_seconds,
        estimated_remaining_seconds=task.estimated_remaining_seconds,
        phase=task.phase,
        processed_search_requests=task.processed_search_requests,
        planned_search_requests=task.planned_search_requests,
        processed_candidates=task.processed_candidates,
        planned_candidate_budget=task.planned_candidate_budget,
        results_url=f"/api/v1/leads?task_id={task.id}" if task.type == ROOT_TASK_TYPE else None,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _review_to_annotation(review: LeadReview) -> LeadReviewAnnotation:
    return LeadReviewAnnotation(
        verdict=review.verdict,
        source_path=review.source_path,
        note=review.note,
        updated_at=review.updated_at,
    )


def lead_to_read(lead: Lead, review_annotations: dict[str, LeadReviewAnnotation] | None = None) -> LeadRead:
    raw_data = dict(lead.raw_data or {})
    payload = {
        "id": lead.id,
        "task_id": lead.task_id,
        "company_name": lead.company_name,
        "website": lead.website,
        "facebook_url": lead.facebook_url,
        "linkedin_url": lead.linkedin_url,
        "country": lead.country,
        "continent": lead.continent,
        "matched_keywords": lead.matched_keywords,
        "source": lead.source,
        "contact_status": lead.contact_status,
        "decision_maker_status": lead.decision_maker_status,
        "general_contact_status": lead.general_contact_status,
        "contact_name": lead.contact_name,
        "contact_title": lead.contact_title,
        "linkedin_personal_url": lead.linkedin_personal_url,
        "personal_email": lead.personal_email,
        "work_email": lead.work_email,
        "phone": lead.phone,
        "whatsapp": lead.whatsapp,
        "potential_contacts": lead.potential_contacts,
        "general_emails": lead.general_emails,
        "field_provenance": raw_data.get("field_provenance"),
        "review_annotations": review_annotations or None,
        "raw_data": raw_data,
        "created_at": lead.created_at,
    }
    return LeadRead.model_validate(payload)


def contact_to_read(contact: Contact) -> ContactRead:
    return ContactRead.model_validate(contact)


def _normalize_keyword_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        keyword = str(value).strip()
        if not keyword:
            continue
        lowered = keyword.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(keyword)
    return normalized


def _task_keywords(task: Task) -> list[str]:
    params = task.params or {}
    keywords = _normalize_keyword_list(params.get("keywords") if isinstance(params.get("keywords"), list) else None)
    if keywords:
        return keywords
    product_name = params.get("product_name")
    if isinstance(product_name, str) and product_name.strip():
        return [product_name.strip()]
    keyword = params.get("keyword")
    if isinstance(keyword, str) and keyword.strip():
        return [keyword.strip()]
    return []


def _child_task_summary(task: Task) -> TaskChildSummaryResponse:
    params = task.params or {}
    keyword = params.get("keyword")
    if not isinstance(keyword, str) or not keyword.strip():
        keyword = None
    cache_hit = bool(params.get("cache_hit")) if params else False
    return TaskChildSummaryResponse(
        id=task.id,
        type=task.type,
        status=_effective_status(task),
        progress=task.progress,
        confirmed_leads=task.confirmed_leads,
        mode=params.get("mode") if params else None,
        keyword=keyword,
        cache_hit=cache_hit,
        updated_at=task.updated_at,
    )


async def get_task(session: AsyncSession, task_id: UUID) -> Task | None:
    return await session.get(Task, task_id)


async def get_root_task(session: AsyncSession, task_id: UUID) -> Task | None:
    task = await session.get(Task, task_id)
    if task is None:
        return None
    if task.type == ROOT_TASK_TYPE or task.parent_task_id is None:
        return task
    return await session.get(Task, task.parent_task_id)


async def get_latest_root_task_id(session: AsyncSession) -> UUID | None:
    result = await session.execute(
        select(Task.id)
        .where(Task.type == ROOT_TASK_TYPE)
        .order_by(Task.updated_at.desc(), Task.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _lead_counts_for_task(session: AsyncSession, task_id: UUID) -> tuple[int, int, int]:
    result = await session.execute(
        select(
            func.count(Lead.id),
            func.coalesce(func.sum(case((Lead.decision_maker_status == "done", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Lead.general_contact_status == "done", 1), else_=0)), 0),
        ).where(Lead.task_id == task_id)
    )
    counts = result.one()
    return int(counts[0] or 0), int(counts[1] or 0), int(counts[2] or 0)


async def _latest_contact_task_summary(session: AsyncSession, task_id: UUID) -> TaskChildSummaryResponse | None:
    result = await session.execute(
        select(Task)
        .where(Task.parent_task_id == task_id, Task.type == CONTACT_TASK_TYPE)
        .order_by(Task.updated_at.desc(), Task.created_at.desc())
        .limit(1)
    )
    child = result.scalar_one_or_none()
    if child is None:
        return None
    return _child_task_summary(child)


async def _keyword_task_summaries(session: AsyncSession, task_id: UUID) -> list[TaskChildSummaryResponse]:
    result = await session.execute(
        select(Task)
        .where(Task.parent_task_id == task_id, Task.type == KEYWORD_TASK_TYPE)
        .order_by(Task.created_at.asc(), Task.updated_at.asc())
    )
    return [_child_task_summary(child) for child in result.scalars().all()]


async def build_task_summary(session: AsyncSession, task: Task) -> TaskSummaryResponse:
    lead_count, decision_done_count, general_done_count = await _lead_counts_for_task(session, task.id)
    latest_contact_task = await _latest_contact_task_summary(session, task.id)
    keyword_tasks = await _keyword_task_summaries(session, task.id)
    keywords = _task_keywords(task)
    if not keywords:
        keywords = [item.keyword for item in keyword_tasks if item.keyword]
    keyword_count = len(keyword_tasks) if keyword_tasks else len(keywords)
    completed_keyword_count = sum(1 for item in keyword_tasks if item.status not in {"pending", "running"})
    if not keyword_tasks and keywords and _effective_status(task) in {"completed", "stopped_early"}:
        completed_keyword_count = len(keywords)
    cache_hit_keyword_count = sum(1 for item in keyword_tasks if item.cache_hit)
    status = task_to_status(task)
    return TaskSummaryResponse(
        **status.model_dump(),
        params=task.params,
        keywords=keywords,
        keyword_count=keyword_count,
        completed_keyword_count=completed_keyword_count,
        cache_hit_keyword_count=cache_hit_keyword_count,
        keyword_tasks=keyword_tasks,
        lead_count=lead_count,
        decision_maker_done_count=decision_done_count,
        general_contact_done_count=general_done_count,
        latest_contact_task=latest_contact_task,
    )


async def get_task_detail(session: AsyncSession, task_id: UUID) -> TaskDetailResponse | None:
    task = await get_root_task(session, task_id)
    if task is None:
        return None
    summary = await build_task_summary(session, task)
    return TaskDetailResponse(**summary.model_dump())


async def get_task_history(
    session: AsyncSession,
    *,
    limit: int = MAX_ROOT_TASK_HISTORY,
    offset: int = 0,
    task_type: str = ROOT_TASK_TYPE,
) -> TaskHistoryListResponse:
    total = int(
        (
            await session.execute(
                select(func.count(Task.id)).where(Task.type == task_type, Task.parent_task_id.is_(None))
            )
        ).scalar_one()
        or 0
    )
    result = await session.execute(
        select(Task)
        .where(Task.type == task_type, Task.parent_task_id.is_(None))
        .order_by(Task.updated_at.desc(), Task.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    tasks = result.scalars().all()
    items = [await build_task_summary(session, task) for task in tasks]
    return TaskHistoryListResponse(items=items, total=total, limit=limit, offset=offset)


async def get_task_leads(
    session: AsyncSession,
    task_id: UUID,
    *,
    page: int = 1,
    page_size: int = 50,
) -> LeadListResponse:
    total = int(
        (
            await session.execute(
                select(func.count(Lead.id)).where(Lead.task_id == task_id)
            )
        ).scalar_one()
        or 0
    )
    result = await session.execute(
        select(Lead)
        .where(Lead.task_id == task_id)
        .order_by(Lead.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    leads = result.scalars().all()
    review_map: dict[UUID, dict[str, LeadReviewAnnotation]] = {}
    lead_ids = [lead.id for lead in leads]
    if lead_ids:
        review_result = await session.execute(
            select(LeadReview).where(LeadReview.lead_id.in_(lead_ids))
        )
        for review in review_result.scalars().all():
            review_map.setdefault(review.lead_id, {})[review.field_key] = _review_to_annotation(review)
    items = [lead_to_read(lead, review_annotations=review_map.get(lead.id)) for lead in leads]
    return LeadListResponse(items=items, total=total, page=page, page_size=page_size)


async def get_all_task_leads(session: AsyncSession, task_id: UUID) -> list[Lead]:
    result = await session.execute(
        select(Lead)
        .where(Lead.task_id == task_id)
        .order_by(Lead.created_at.asc())
    )
    return result.scalars().all()


async def get_lead_with_contacts(session: AsyncSession, lead_id: UUID) -> Lead | None:
    result = await session.execute(
        select(Lead)
        .options(selectinload(Lead.contacts))
        .where(Lead.id == lead_id)
    )
    return result.scalar_one_or_none()


async def get_contact_list(session: AsyncSession, lead_id: UUID) -> list[ContactRead]:
    result = await session.execute(
        select(Contact)
        .where(Contact.lead_id == lead_id)
        .order_by(Contact.created_at.asc())
    )
    return [contact_to_read(contact) for contact in result.scalars().all()]


async def cleanup_old_root_tasks(session: AsyncSession, *, keep: int = MAX_ROOT_TASK_HISTORY) -> None:
    stale_result = await session.execute(
        select(Task.id)
        .where(
            Task.type == ROOT_TASK_TYPE,
            Task.parent_task_id.is_(None),
            Task.status.notin_(("pending", "running")),
        )
        .order_by(Task.updated_at.desc(), Task.created_at.desc())
        .offset(keep)
    )
    stale_ids = list(stale_result.scalars().all())
    if not stale_ids:
        return
    await session.execute(delete(Task).where(Task.id.in_(stale_ids)))
