import math
from datetime import datetime, timezone
from io import BytesIO, StringIO
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from fastapi.responses import Response, StreamingResponse
from openpyxl import Workbook

from app.schemas.contact import ContactRead
from app.schemas.lead import LeadListResponse, LeadRead, LeadSearchRequest
from app.schemas.task import TaskCreateResponse, TaskStatusResponse
from app.services.search.serper import SerperClient

router = APIRouter(prefix="/leads", tags=["leads"])
OVERSEARCH_MULTIPLIER = 1.5

TASKS: dict[str, dict] = {}
LEADS: dict[str, list[LeadRead]] = {}
CONTACTS: dict[str, list[ContactRead]] = {}
CHANNEL_POOL = ["google", "facebook", "linkedin", "yellowpages"]
IGNORED_HOSTS = {"example.com", "example.org", "example.net", "linkedin.com", "www.linkedin.com", "facebook.com", "www.facebook.com"}


def should_stop(confirmed_count: int, target: int | None) -> bool:
    if target is None:
        return False
    return confirmed_count >= target


def _normalize_company_name(title: str | None, host: str) -> str:
    if title:
        for separator in ["|", "-", "–", "—"]:
            if separator in title:
                title = title.split(separator)[0].strip()
                break
        if title:
            return title
    domain = host.removeprefix("www.")
    return domain.split(".")[0].replace("-", " ").title()


async def _fetch_search_results(payload: LeadSearchRequest) -> list[dict]:
    serper_client = SerperClient()
    target = payload.target_count or 10
    max_results = max(1, math.ceil(target * OVERSEARCH_MULTIPLIER))
    countries = payload.countries or [""]
    queries = [f"{payload.product_name} supplier {country}".strip() for country in countries[:3]]
    language = payload.languages[0] if payload.languages else "en"

    collected: list[dict] = []
    seen_hosts: set[str] = set()

    async def add_result(url: str | None, title: str | None, snippet: str | None, source: str, country: str | None) -> None:
        if not url:
            return
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if not host or host in seen_hosts or host in IGNORED_HOSTS:
            return
        seen_hosts.add(host)
        collected.append({
            "company_name": _normalize_company_name(title, host),
            "website": f"{parsed.scheme or 'https'}://{host}",
            "facebook_url": url if "facebook.com" in host else None,
            "linkedin_url": url if "linkedin.com" in host else None,
            "country": country,
            "continent": payload.continents[0] if payload.continents else None,
            "source": source,
            "contact_status": "pending",
            "contact_name": None,
            "contact_title": None,
            "personal_email": None,
            "work_email": None,
            "phone": None,
            "whatsapp": None,
            "raw_data": {"snippet": snippet, "source": source},
        })

    for query_index, query in enumerate(queries):
        country = countries[query_index] if query_index < len(countries) else None
        serper_data = await serper_client.search(query=query, hl=language, num=max_results)
        for item in serper_data.get("organic", []):
            await add_result(item.get("link"), item.get("title"), item.get("snippet"), "google", country)
            if should_stop(len(collected), payload.target_count) or len(collected) >= max_results:
                return collected

    return collected


def build_task_status(task: dict) -> TaskStatusResponse:
    now = datetime.now(timezone.utc)
    stopped_early = should_stop(task["confirmed_leads"], task["target_count"])
    status = "stopped_early" if stopped_early else task["status"]
    progress = 100 if status in {"completed", "stopped_early"} else task["progress"]
    task.update({"status": status, "progress": progress, "stopped_early": stopped_early, "updated_at": now})
    return TaskStatusResponse(
        id=task["id"],
        status=status,
        progress=progress,
        total=task["total"],
        completed=task["completed"],
        confirmed_leads=task["confirmed_leads"],
        target_count=task["target_count"],
        stopped_early=stopped_early,
        estimated_remaining_seconds=0,
        results_url=f"/api/v1/leads?task_id={task['id']}",
        created_at=task["created_at"],
        updated_at=task["updated_at"],
    )


@router.post("/search", response_model=TaskCreateResponse)
async def create_lead_search(payload: LeadSearchRequest) -> TaskCreateResponse:
    task_id = uuid4()
    now = datetime.now(timezone.utc)
    results = await _fetch_search_results(payload)
    target_count = payload.target_count
    confirmed_leads = len(results) if target_count is None else min(len(results), target_count)
    total = math.ceil(target_count * OVERSEARCH_MULTIPLIER) if target_count else len(results)
    total = max(total, confirmed_leads)

    TASKS[str(task_id)] = {
        "id": task_id,
        "status": "completed",
        "progress": 100,
        "total": total,
        "completed": total,
        "confirmed_leads": confirmed_leads,
        "target_count": target_count,
        "stopped_early": should_stop(confirmed_leads, target_count),
        "created_at": now,
        "updated_at": now,
    }

    LEADS[str(task_id)] = [
        LeadRead(
            id=uuid4(),
            task_id=task_id,
            company_name=item["company_name"],
            website=item["website"],
            facebook_url=item["facebook_url"],
            linkedin_url=item["linkedin_url"],
            country=item["country"],
            continent=item["continent"],
            source=item["source"],
            contact_status=item["contact_status"],
            contact_name=item["contact_name"],
            contact_title=item["contact_title"],
            personal_email=item["personal_email"],
            work_email=item["work_email"],
            phone=item["phone"],
            whatsapp=item["whatsapp"],
            raw_data=item["raw_data"],
            created_at=now,
        )
        for item in results[:confirmed_leads]
    ]
    return TaskCreateResponse(task_id=task_id)


@router.get("", response_model=LeadListResponse)
async def list_leads(task_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)) -> LeadListResponse:
    items = LEADS.get(str(task_id), [])
    start = (page - 1) * page_size
    end = start + page_size
    return LeadListResponse(items=items[start:end], total=len(items), page=page, page_size=page_size)


@router.get("/export")
async def export_leads(task_id: UUID, format: str = "xlsx", include_contacts: bool = False):
    leads = LEADS.get(str(task_id), [])
    if format == "csv":
        buffer = StringIO()
        headers = ["company_name", "website", "facebook_url", "linkedin_url", "country", "status"]
        if include_contacts:
            headers += ["contact_name", "contact_title", "personal_email", "work_email", "phone", "whatsapp"]
        buffer.write(",".join(headers) + "\n")
        for lead in leads:
            row = [lead.company_name or "", lead.website or "", lead.facebook_url or "", lead.linkedin_url or "", lead.country or "", lead.contact_status]
            if include_contacts:
                row += [lead.contact_name or "", lead.contact_title or "", lead.personal_email or "", lead.work_email or "", lead.phone or "", lead.whatsapp or ""]
            buffer.write(",".join(row) + "\n")
        return Response(content=buffer.getvalue(), media_type="text/csv")

    workbook = Workbook()
    sheet = workbook.active
    headers = ["company_name", "website", "facebook_url", "linkedin_url", "country", "status"]
    if include_contacts:
        headers += ["contact_name", "contact_title", "personal_email", "work_email", "phone", "whatsapp"]
    sheet.append(headers)
    for lead in leads:
        row = [lead.company_name, lead.website, lead.facebook_url, lead.linkedin_url, lead.country, lead.contact_status]
        if include_contacts:
            row += [lead.contact_name, lead.contact_title, lead.personal_email, lead.work_email, lead.phone, lead.whatsapp]
        sheet.append(row)
    data = BytesIO()
    workbook.save(data)
    data.seek(0)
    return StreamingResponse(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.delete("")
async def delete_leads(task_id: UUID) -> dict:
    TASKS.pop(str(task_id), None)
    LEADS.pop(str(task_id), None)
    return {"deleted": True}
