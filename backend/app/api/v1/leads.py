import asyncio
import math
from datetime import datetime, timezone
from io import BytesIO, StringIO
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from fastapi.responses import Response, StreamingResponse
from openpyxl import Workbook

from app.schemas.contact import ContactRead
from app.schemas.lead import LeadListResponse, LeadRead, LeadSearchRequest
from app.schemas.task import TaskCreateResponse, TaskStatusResponse

router = APIRouter(prefix="/leads", tags=["leads"])
OVERSEARCH_MULTIPLIER = 1.5

TASKS: dict[str, dict] = {}
LEADS: dict[str, list[LeadRead]] = {}
CONTACTS: dict[str, list[ContactRead]] = {}

CHANNEL_POOL = ["google", "bing", "facebook", "linkedin", "yellowpages"]


def should_stop(confirmed_count: int, target: int | None) -> bool:
    if target is None:
        return False
    return confirmed_count >= target


def _lead_templates(product_name: str, countries: list[str], continents: list[str]) -> list[dict]:
    fallback_countries = countries or ["US", "DE", "JP", "BR", "ZA"]
    fallback_continent = continents[0] if continents else "Global"
    templates = []
    for index, country in enumerate(fallback_countries[:5], start=1):
        templates.append({
            "company_name": f"{product_name.title()} Prospect {index}",
            "website": f"https://example{index}.com",
            "facebook_url": f"https://facebook.com/example{index}" if index % 2 else None,
            "linkedin_url": f"https://linkedin.com/company/example-{index}",
            "country": country,
            "continent": fallback_continent,
            "source": CHANNEL_POOL[(index - 1) % len(CHANNEL_POOL)],
            "contact_status": "completed" if index <= 2 else "pending",
            "contact_name": ["Alex Morgan", "Jamie Chen", "Taylor Singh", None, None][index - 1],
            "contact_title": ["Managing Director", "Procurement Manager", "General Manager", None, None][index - 1],
            "personal_email": ["alex@example.com", None, None, None, None][index - 1],
            "work_email": ["amorgan@example.com", "jamie.chen@example.com", None, None, None][index - 1],
            "phone": ["+1 202-555-0101", "+49 30-123456", None, None, None][index - 1],
            "whatsapp": ["+1 202-555-0101", None, None, None, None][index - 1],
        })
    return templates


def build_task_status(task: dict) -> TaskStatusResponse:
    now = datetime.now(timezone.utc)
    elapsed = max(int((now - task["created_at"]).total_seconds()), 0)
    total = max(task["total"], 1)
    completed = min(total, max(1, elapsed // 2 + 1))
    confirmed_goal = task["target_count"] if task["target_count"] is not None else task["final_confirmed_leads"]
    confirmed_leads = min(task["final_confirmed_leads"], max(0, round(completed / total * confirmed_goal)))
    stopped_early = should_stop(confirmed_leads, task["target_count"])

    if stopped_early:
        status = "stopped_early"
        completed = min(completed, task["total"])
        progress = 100
    elif completed >= total:
        status = "completed"
        confirmed_leads = task["final_confirmed_leads"]
        progress = 100
    else:
        status = "running"
        progress = min(99, int(completed / total * 100))

    remaining = 0 if status in {"completed", "stopped_early"} else max(total * 2 - elapsed, 0)
    task.update({
        "status": status,
        "progress": progress,
        "completed": completed,
        "confirmed_leads": confirmed_leads,
        "stopped_early": stopped_early,
        "updated_at": now,
    })
    return TaskStatusResponse(
        id=task["id"],
        status=status,
        progress=progress,
        total=task["total"],
        completed=completed,
        confirmed_leads=confirmed_leads,
        target_count=task["target_count"],
        stopped_early=stopped_early,
        estimated_remaining_seconds=remaining,
        results_url=f"/api/v1/leads?task_id={task['id']}",
        created_at=task["created_at"],
        updated_at=task["updated_at"],
    )


@router.post("/search", response_model=TaskCreateResponse)
async def create_lead_search(payload: LeadSearchRequest) -> TaskCreateResponse:
    task_id = uuid4()
    now = datetime.now(timezone.utc)
    templates = _lead_templates(payload.product_name, payload.countries, payload.continents)
    target_count = payload.target_count
    total = math.ceil(target_count * OVERSEARCH_MULTIPLIER) if target_count else max(len(templates), 5)
    final_confirmed = min(len(templates), target_count) if target_count else len(templates)

    TASKS[str(task_id)] = {
        "id": task_id,
        "status": "running",
        "progress": 0,
        "total": total,
        "completed": 0,
        "confirmed_leads": 0,
        "target_count": target_count,
        "stopped_early": False,
        "created_at": now,
        "updated_at": now,
        "final_confirmed_leads": final_confirmed,
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
            raw_data={"product_name": payload.product_name, "languages": payload.languages, "channels": CHANNEL_POOL},
            created_at=now,
        )
        for item in templates[:final_confirmed]
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
