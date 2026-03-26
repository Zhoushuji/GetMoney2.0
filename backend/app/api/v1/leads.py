import asyncio
import csv
import math
from datetime import datetime, timezone
from io import BytesIO, StringIO
from urllib.parse import urlparse
from uuid import UUID

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models.lead import Lead
from app.models.task import Task
from app.schemas.lead import LeadListResponse, LeadSearchRequest
from app.schemas.task import TaskCreateResponse
from app.services.extraction.company_name import CompanyNameExtractor
from app.services.extraction.country_detection import (
    CountryDetector,
    country_gl,
    preferred_country_search_term,
    resolve_country,
)
from app.services.extraction.social_links import SocialLinksExtractor
from app.services.search.serper import SerperClient
from app.services.workspace_store import (
    ROOT_TASK_TYPE,
    cleanup_old_root_tasks,
    get_root_task,
    get_task_leads,
)

router = APIRouter(prefix="/leads", tags=["leads"])

SETTINGS = get_settings()
IGNORED_HOSTS = {"example.com", "example.org", "example.net", "linkedin.com", "www.linkedin.com", "facebook.com", "www.facebook.com"}
DEMO_SUFFIXES = [
    "Trading",
    "Manufacturing",
    "Supply",
    "Industries",
    "Global",
    "Solutions",
    "Exports",
    "Partners",
]
QUERY_TEMPLATES = [
    "{product} supplier in {country}",
    "{product} manufacturer in {country}",
    "{product} factory in {country}",
    "{product} exporter in {country}",
    "{product} wholesaler in {country}",
    "{product} company in {country}",
]
AVG_SERPER_PAGE_SECONDS = 1.5
AVG_CANDIDATE_BUILD_SECONDS = 5.0
FINALIZE_SECONDS = 2
DEMO_TOTAL_SECONDS = 2


class SearchRuntime:
    def __init__(self) -> None:
        self.settings = SETTINGS
        self.serper_client = SerperClient()
        self.search_semaphore = asyncio.Semaphore(max(1, self.settings.max_concurrent_searches))
        self.scrape_semaphore = asyncio.Semaphore(max(1, self.settings.max_concurrent_scrapers))


async def _safe_serper_search(serper_client: SerperClient, query: str, hl: str, gl: str, num: int, page: int = 1) -> dict:
    try:
        return await serper_client.search(query=query, hl=hl, gl=gl, num=num, page=page)
    except Exception:
        return {"organic": []}


async def _fetch_homepage(website: str, timeout: float = 15.0) -> tuple[BeautifulSoup | None, str | None]:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(website, headers={"User-Agent": "Mozilla/5.0 LeadGenBot/1.0"})
            response.raise_for_status()
    except Exception:
        return None, None
    return BeautifulSoup(response.text, "html.parser"), response.text


def _build_queries(payload: LeadSearchRequest) -> list[dict[str, str]]:
    countries = payload.countries or [""]
    languages = payload.languages or ["en"]
    queries: list[dict[str, str]] = []
    for country in countries:
        for language in languages:
            query_country = preferred_country_search_term(country, language) or country
            gl = country_gl(country)
            for template in QUERY_TEMPLATES:
                if query_country:
                    query = template.format(product=payload.product_name, country=query_country).strip()
                else:
                    query = template.replace(" in {country}", "").format(product=payload.product_name, country="").strip()
                queries.append({
                    "country": country,
                    "language": language,
                    "gl": gl,
                    "query": query,
                })
    return queries


def _max_pages(target_count: int | None) -> int:
    if target_count is None:
        return 3
    return max(1, min(10, math.ceil(target_count / 50)))


def _pages_per_query(payload: LeadSearchRequest) -> int:
    pages = _max_pages(payload.target_count)
    if payload.mode == "live" and payload.countries:
        return max(2, pages)
    return pages


def _slugify(value: str) -> str:
    slug = "".join(character.lower() if character.isalnum() else " " for character in value)
    return "-".join(part for part in slug.split() if part) or "product"


def _demo_result_count(payload: LeadSearchRequest) -> int:
    if payload.target_count is not None:
        return payload.target_count
    country_count = len(payload.countries) if payload.countries else 1
    language_count = len(payload.languages) if payload.languages else 1
    return max(6, min(12, country_count * language_count * 2))


def _estimate_total_leads(payload: LeadSearchRequest) -> int:
    if payload.mode == "demo":
        return _demo_result_count(payload)
    if payload.target_count is not None:
        return max(payload.target_count, payload.target_count * 2)
    query_count = max(1, len(_build_queries(payload)))
    estimated = query_count * _pages_per_query(payload) * 10
    return max(estimated, 10)


def _initial_candidate_budget(target_count: int | None, query_count: int, pages_per_query: int) -> int:
    if target_count is None:
        return min(query_count * pages_per_query * 10, query_count * 30)
    return max(target_count, target_count * 2)


def _candidate_budget_step(target_count: int | None, query_count: int) -> int:
    if target_count is None:
        return max(10, query_count * 5)
    return max(1, target_count)


def _estimate_search_runtime(payload: LeadSearchRequest, candidate_budget_override: int | None = None) -> dict[str, int]:
    if payload.mode == "demo":
        planned_candidate_budget = candidate_budget_override or _demo_result_count(payload)
        return {
            "planned_search_requests": 0,
            "planned_candidate_budget": planned_candidate_budget,
            "estimated_total_seconds": DEMO_TOTAL_SECONDS,
        }
    queries = _build_queries(payload)
    query_count = max(1, len(queries))
    pages_per_query = _pages_per_query(payload)
    planned_search_requests = query_count * pages_per_query
    planned_candidate_budget = candidate_budget_override or _initial_candidate_budget(payload.target_count, query_count, pages_per_query)
    search_seconds = math.ceil(planned_search_requests / max(1, SETTINGS.max_concurrent_searches)) * AVG_SERPER_PAGE_SECONDS
    candidate_seconds = planned_candidate_budget * AVG_CANDIDATE_BUILD_SECONDS
    estimated_total_seconds = max(1, int(math.ceil(search_seconds + candidate_seconds + FINALIZE_SECONDS)))
    return {
        "planned_search_requests": planned_search_requests,
        "planned_candidate_budget": planned_candidate_budget,
        "estimated_total_seconds": estimated_total_seconds,
    }


def _build_demo_lead_item(payload: LeadSearchRequest, index: int) -> dict:
    countries = payload.countries or ["Global Market"]
    continents = payload.continents or ["Global"]
    languages = payload.languages or ["en"]
    country = countries[index % len(countries)]
    continent = continents[index % len(continents)]
    language = languages[index % len(languages)]
    suffix = DEMO_SUFFIXES[index % len(DEMO_SUFFIXES)]
    slug = _slugify(payload.product_name)
    country_slug = _slugify(country)
    company_name = f"{payload.product_name.strip()} {suffix} {index + 1}".strip()
    website = f"https://example.com/demo/{slug}/{country_slug}/{index + 1}"
    target_country = resolve_country(country)
    return {
        "company_name": company_name,
        "website": website,
        "facebook_url": f"https://www.facebook.com/{slug}-{index + 1}",
        "linkedin_url": f"https://www.linkedin.com/company/{slug}-{country_slug}-{index + 1}",
        "country": country,
        "continent": continent,
        "source": "demo",
        "contact_status": "pending",
        "decision_maker_status": "pending",
        "general_contact_status": "pending",
        "contact_name": None,
        "contact_title": None,
        "linkedin_personal_url": None,
        "personal_email": None,
        "work_email": None,
        "phone": None,
        "whatsapp": None,
        "potential_contacts": None,
        "general_emails": [],
        "raw_data": {
            "search_title": company_name,
            "search_snippet": f"Demo lead generated for {payload.product_name} in {country}.",
            "name_source": "demo_mode",
            "demo_mode": True,
            "demo_index": index + 1,
            "demo_language": language,
            "target_country": target_country.name_en if target_country is not None else country,
            "target_country_code": target_country.code if target_country is not None else None,
            "country_detection": {
                "status": "matched",
                "target_country_code": target_country.code if target_country is not None else None,
                "target_country_name": target_country.name_en if target_country is not None else country,
                "detected_country_code": target_country.code if target_country is not None else None,
                "detected_country_name": target_country.name_en if target_country is not None else country,
                "continent": continent,
                "confidence": 1.0,
                "evidence": [{"country_code": target_country.code if target_country is not None else None, "country_name": country, "signal": "demo_mode", "value": country, "weight": 100}],
                "mismatch_reason": None,
            },
        },
    }


def _build_demo_leads(payload: LeadSearchRequest) -> list[dict]:
    result_count = _demo_result_count(payload)
    return [_build_demo_lead_item(payload, index) for index in range(result_count)]


def _task_payload(task: Task) -> LeadSearchRequest:
    params = task.params or {}
    return LeadSearchRequest(
        product_name=params.get("product_name", ""),
        continents=params.get("continents") or [],
        countries=params.get("countries") or [],
        languages=params.get("languages") or [],
        target_count=task.target_count,
        mode=params.get("mode", "live"),
    )


def _refresh_search_task_projection(task: Task) -> None:
    payload = _task_payload(task)
    plan = _estimate_search_runtime(payload, candidate_budget_override=task.planned_candidate_budget or None)
    task.planned_search_requests = plan["planned_search_requests"]
    task.planned_candidate_budget = plan["planned_candidate_budget"]
    task.estimated_total_seconds = plan["estimated_total_seconds"]
    task.total = max(task.total, task.planned_candidate_budget)
    if task.status in {"completed", "failed"}:
        task.progress = 100 if task.status == "completed" else task.progress
        task.estimated_remaining_seconds = 0
        if task.status == "completed":
            task.phase = "completed"
        elif task.status == "failed":
            task.phase = "failed"
        return
    if payload.mode == "demo":
        task.estimated_remaining_seconds = DEMO_TOTAL_SECONDS
        task.progress = 0
        task.completed = 0
        return
    completed_estimated_seconds = (
        (task.processed_search_requests / max(1, SETTINGS.max_concurrent_searches)) * AVG_SERPER_PAGE_SECONDS
        + task.processed_candidates * AVG_CANDIDATE_BUILD_SECONDS
    )
    estimated_total = max(1, task.estimated_total_seconds or 1)
    task.estimated_remaining_seconds = max(0, int(math.ceil(estimated_total - completed_estimated_seconds)))
    task.progress = min(99, int(round((min(completed_estimated_seconds, estimated_total) / estimated_total) * 100)))
    task.completed = task.processed_candidates


async def _mutate_search_task(
    task_id: UUID,
    *,
    phase: str | None = None,
    status: str | None = None,
    processed_search_requests_inc: int = 0,
    processed_candidates_inc: int = 0,
    planned_candidate_budget: int | None = None,
    confirmed_leads: int | None = None,
    stopped_early: bool | None = None,
    error: str | None = None,
) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(Task).where(Task.id == task_id).with_for_update())
        task = result.scalar_one_or_none()
        if task is None:
            return
        if phase is not None:
            task.phase = phase
        if status is not None:
            task.status = status
        if processed_search_requests_inc:
            task.processed_search_requests += processed_search_requests_inc
        if processed_candidates_inc:
            task.processed_candidates += processed_candidates_inc
        if planned_candidate_budget is not None:
            task.planned_candidate_budget = planned_candidate_budget
        if confirmed_leads is not None:
            task.confirmed_leads = confirmed_leads
        if stopped_early is not None:
            task.stopped_early = stopped_early
        if error is not None:
            task.error = error
        task.updated_at = datetime.now(timezone.utc)
        _refresh_search_task_projection(task)
        await session.commit()


async def _persist_search_results(task_id: UUID, results: list[dict], *, confirmed_leads: int, stopped_early: bool) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(Task).where(Task.id == task_id).with_for_update())
        task = result.scalar_one_or_none()
        if task is None:
            return
        now = datetime.now(timezone.utc)
        session.add_all([Lead(task_id=task_id, created_at=now, **item) for item in results[:confirmed_leads]])
        task.status = "completed"
        task.phase = "completed"
        task.progress = 100
        task.completed = task.processed_candidates or len(results)
        task.confirmed_leads = confirmed_leads
        task.stopped_early = stopped_early
        task.estimated_remaining_seconds = 0
        task.updated_at = now
        await session.commit()


async def _mark_search_failed(task_id: UUID, exc: Exception) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(Task).where(Task.id == task_id).with_for_update())
        task = result.scalar_one_or_none()
        if task is None:
            return
        task.status = "failed"
        task.phase = "failed"
        task.error = str(exc)
        task.estimated_remaining_seconds = 0
        task.updated_at = datetime.now(timezone.utc)
        await session.commit()


async def _search_serper_paginated(runtime: SearchRuntime, task_id: UUID, query: str, gl: str, hl: str, max_pages: int) -> list[dict]:
    results: list[dict] = []
    async with runtime.search_semaphore:
        for page in range(1, max_pages + 1):
            data = await _safe_serper_search(runtime.serper_client, query=query, hl=hl, gl=gl, num=10, page=page)
            await _mutate_search_task(task_id, phase="querying", processed_search_requests_inc=1)
            organic = data.get("organic", [])
            results.extend(organic)
            if len(organic) < 10:
                break
    return results


async def _build_lead_item(runtime: SearchRuntime, serper_item: dict, country: str) -> dict | None:
    url = serper_item.get("link")
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not host or host in IGNORED_HOSTS:
        return None
    website = f"{parsed.scheme or 'https'}://{host}"

    async with runtime.scrape_semaphore:
        _, html = await _fetch_homepage(website)
    domain = parsed.netloc.removeprefix("www.")
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        name_extractor = CompanyNameExtractor(http_client=client)
        country_detector = CountryDetector(http_client=client)
        social_extractor = SocialLinksExtractor(http_client=client)
        company_name, detection = await asyncio.gather(
            name_extractor.extract(website, serper_result=serper_item, homepage_html=html),
            country_detector.detect(
                website=website,
                target_country=country,
                search_title=serper_item.get("title"),
                search_snippet=serper_item.get("snippet"),
                homepage_html=html,
            ),
        )
        target_country = resolve_country(country)
        if target_country is not None and detection.status != "matched":
            return None
        social_links = await social_extractor.extract((serper_item.get("knowledgeGraph", {}) or {}).get("title", company_name or domain), domain)
    return {
        "company_name": company_name,
        "website": website,
        "facebook_url": social_links.get("facebook"),
        "linkedin_url": social_links.get("linkedin"),
        "country": detection.detected_country_name,
        "continent": detection.continent,
        "source": "google",
        "contact_status": "pending",
        "decision_maker_status": "pending",
        "general_contact_status": "pending",
        "contact_name": None,
        "contact_title": None,
        "linkedin_personal_url": None,
        "personal_email": None,
        "work_email": None,
        "phone": None,
        "whatsapp": None,
        "potential_contacts": None,
        "general_emails": [],
        "raw_data": {
            "search_title": serper_item.get("title"),
            "search_snippet": serper_item.get("snippet"),
            "name_source": "extraction_v22",
            "target_country": target_country.name_en if target_country is not None else country,
            "target_country_code": target_country.code if target_country is not None else None,
            "country_detection": detection.as_dict(),
        },
    }


async def _fetch_search_results(task_id: UUID, payload: LeadSearchRequest) -> list[dict]:
    runtime = SearchRuntime()
    queries = _build_queries(payload)
    pages_per_query = _pages_per_query(payload)
    paged_results = await asyncio.gather(*[
        _search_serper_paginated(
            runtime,
            task_id,
            query=item["query"],
            gl=item["gl"],
            hl=item["language"],
            max_pages=pages_per_query,
        )
        for item in queries
    ])

    await _mutate_search_task(task_id, phase="building_leads")
    collected: list[dict] = []
    seen_hosts: set[str] = set()
    max_results = payload.target_count or len(queries) * 30
    candidate_budget = _initial_candidate_budget(payload.target_count, max(1, len(queries)), pages_per_query)
    budget_step = _candidate_budget_step(payload.target_count, max(1, len(queries)))
    inspected_candidates = 0

    for query_info, search_results in zip(queries, paged_results, strict=False):
        for item in search_results:
            inspected_candidates += 1
            if inspected_candidates > candidate_budget:
                if payload.target_count and len(collected) >= payload.target_count:
                    return collected[:payload.target_count]
                candidate_budget += budget_step
                await _mutate_search_task(task_id, planned_candidate_budget=candidate_budget)
            lead_item = await _build_lead_item(runtime, item, query_info["country"])
            await _mutate_search_task(task_id, processed_candidates_inc=1)
            if not lead_item:
                continue
            host = urlparse(lead_item["website"]).netloc.lower()
            if host in seen_hosts:
                continue
            seen_hosts.add(host)
            collected.append(lead_item)
            await _mutate_search_task(task_id, confirmed_leads=len(collected))
            if payload.target_count and len(collected) >= payload.target_count:
                return collected
            if len(collected) >= max_results:
                return collected
    return collected


async def _run_lead_search_task(task_id: UUID, payload: LeadSearchRequest) -> None:
    try:
        await _mutate_search_task(task_id, status="running", phase="querying")
        if payload.mode == "demo":
            results = _build_demo_leads(payload)
            confirmed_leads = len(results)
            stopped_early = False
        else:
            results = await _fetch_search_results(task_id, payload)
            confirmed_leads = len(results) if payload.target_count is None else min(len(results), payload.target_count)
            stopped_early = payload.target_count is not None and confirmed_leads >= payload.target_count
        await _persist_search_results(task_id, results, confirmed_leads=confirmed_leads, stopped_early=stopped_early)
    except Exception as exc:
        await _mark_search_failed(task_id, exc)


def _style_workbook(sheet) -> None:
    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True)
    center_alignment = Alignment(vertical="center", wrap_text=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_alignment
    widths = {"A": 24, "B": 30, "C": 26, "D": 28, "E": 18, "F": 16, "G": 22, "H": 22, "I": 24, "J": 28, "K": 20, "L": 20, "M": 30}
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)


@router.post("/search", response_model=TaskCreateResponse)
async def create_lead_search(payload: LeadSearchRequest, db: AsyncSession = Depends(get_db)) -> TaskCreateResponse:
    runtime_plan = _estimate_search_runtime(payload)
    now = datetime.now(timezone.utc)
    task = Task(
        type=ROOT_TASK_TYPE,
        status="pending",
        progress=0,
        total=runtime_plan["planned_candidate_budget"],
        completed=0,
        target_count=payload.target_count,
        confirmed_leads=0,
        stopped_early=False,
        params={
            "product_name": payload.product_name,
            "continents": payload.continents,
            "countries": payload.countries,
            "languages": payload.languages,
            "mode": payload.mode,
        },
        estimated_total_seconds=runtime_plan["estimated_total_seconds"],
        estimated_remaining_seconds=runtime_plan["estimated_total_seconds"],
        phase="queued",
        processed_search_requests=0,
        planned_search_requests=runtime_plan["planned_search_requests"],
        processed_candidates=0,
        planned_candidate_budget=runtime_plan["planned_candidate_budget"],
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    await cleanup_old_root_tasks(db)
    await db.commit()

    asyncio.create_task(_run_lead_search_task(task.id, payload.model_copy(deep=True)))
    return TaskCreateResponse(task_id=task.id)


@router.get("", response_model=LeadListResponse)
async def list_leads(
    task_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> LeadListResponse:
    return await get_task_leads(db, task_id, page=page, page_size=page_size)


@router.get("/export")
async def export_leads(task_id: UUID, format: str = "xlsx", include_contacts: bool = False, db: AsyncSession = Depends(get_db)):
    lead_page = await get_task_leads(db, task_id, page=1, page_size=200)
    leads = lead_page.items
    while len(leads) < lead_page.total:
        next_page = (len(leads) // 200) + 1
        next_items = await get_task_leads(db, task_id, page=next_page, page_size=200)
        leads.extend(next_items.items)

    headers = ["company_name", "website", "facebook_url", "linkedin_url", "detected_country", "status", "name_source"]
    if include_contacts:
        headers += ["contact_name", "contact_title", "personal_email", "work_email", "phone", "whatsapp", "potential_contacts"]
    if format == "csv":
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        for lead in leads:
            row = [lead.company_name or "", lead.website or "", lead.facebook_url or "", lead.linkedin_url or "", lead.country or "", lead.contact_status, (lead.raw_data or {}).get("name_source", "")]
            if include_contacts:
                row += [lead.contact_name or "", lead.contact_title or "", lead.personal_email or "", lead.work_email or "", lead.phone or "", lead.whatsapp or "", "; ".join((lead.potential_contacts or {}).get("items", []))]
            writer.writerow(row)
        return Response(content=buffer.getvalue(), media_type="text/csv")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Lead Results"
    pretty_headers = ["Company Name", "Website", "Facebook URL", "LinkedIn URL", "Detected Country", "Status", "Name Source"]
    if include_contacts:
        pretty_headers += ["Contact Name", "Contact Title", "Personal Email", "Work Email", "Phone", "WhatsApp", "Potential Contacts"]
    sheet.append(pretty_headers)
    for lead in leads:
        row = [lead.company_name, lead.website, lead.facebook_url, lead.linkedin_url, lead.country, lead.contact_status, (lead.raw_data or {}).get("name_source")]
        if include_contacts:
            row += [lead.contact_name, lead.contact_title, lead.personal_email, lead.work_email, lead.phone, lead.whatsapp, "\n".join((lead.potential_contacts or {}).get("items", []))]
        sheet.append(row)
    _style_workbook(sheet)
    data = BytesIO()
    workbook.save(data)
    data.seek(0)
    return StreamingResponse(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.delete("")
async def delete_leads(task_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    task = await get_root_task(db, task_id)
    if task is not None:
        await db.delete(task)
        await db.commit()
    return {"deleted": True}
