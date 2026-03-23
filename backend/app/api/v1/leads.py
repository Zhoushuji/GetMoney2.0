from datetime import datetime, timezone
from io import BytesIO, StringIO
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from fastapi.responses import Response, StreamingResponse
from openpyxl import Workbook

from app.schemas.contact import ContactRead
from app.schemas.lead import LeadListResponse, LeadRead, LeadSearchRequest
from app.schemas.task import TaskCreateResponse

router = APIRouter(prefix="/leads", tags=["leads"])

TASKS: dict[str, dict] = {}
LEADS: dict[str, list[LeadRead]] = {}
CONTACTS: dict[str, list[ContactRead]] = {}


@router.post("/search", response_model=TaskCreateResponse)
async def create_lead_search(payload: LeadSearchRequest) -> TaskCreateResponse:
    task_id = uuid4()
    now = datetime.now(timezone.utc)
    TASKS[str(task_id)] = {
        "id": task_id,
        "status": "completed",
        "progress": 100,
        "total": 3,
        "completed": 3,
        "created_at": now,
        "updated_at": now,
    }
    LEADS[str(task_id)] = [
        LeadRead(
            id=uuid4(),
            task_id=task_id,
            company_name=f"{payload.product_name.title()} Global Trading",
            website="https://example.com",
            facebook_url="https://facebook.com/example",
            linkedin_url="https://linkedin.com/company/example",
            country=payload.countries[0] if payload.countries else "United States",
            continent=payload.continents[0] if payload.continents else "North America",
            source=(payload.channels or ["google"])[0],
            contact_status="pending",
            raw_data={"product_name": payload.product_name, "languages": payload.languages},
            created_at=now,
        ),
        LeadRead(
            id=uuid4(),
            task_id=task_id,
            company_name=f"{payload.product_name.title()} Industrial Supply",
            website="https://example.org",
            facebook_url=None,
            linkedin_url="https://linkedin.com/company/example-org",
            country=payload.countries[1] if len(payload.countries) > 1 else "Germany",
            continent=payload.continents[0] if payload.continents else "Europe",
            source="bing",
            contact_status="in_progress",
            raw_data={"channels": payload.channels},
            created_at=now,
        ),
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
        headers = ["company_name", "website", "facebook_url", "linkedin_url", "country", "source", "status"]
        if include_contacts:
            headers += ["contact_name", "contact_title", "personal_email", "work_email", "phone", "whatsapp", "contact_confidence"]
        buffer.write(",".join(headers) + "\n")
        for lead in leads:
            row = [lead.company_name or "", lead.website or "", lead.facebook_url or "", lead.linkedin_url or "", lead.country or "", lead.source or "", lead.contact_status]
            if include_contacts:
                contact = (CONTACTS.get(str(lead.id)) or [None])[0]
                row += [
                    contact.person_name if contact else "",
                    contact.title if contact else "",
                    contact.personal_email if contact else "",
                    contact.work_email if contact else "",
                    contact.phone if contact else "",
                    contact.whatsapp if contact else "",
                    str(contact.confidence) if contact else "",
                ]
            buffer.write(",".join(row) + "\n")
        return Response(content=buffer.getvalue(), media_type="text/csv")

    workbook = Workbook()
    sheet = workbook.active
    headers = ["company_name", "website", "facebook_url", "linkedin_url", "country", "source", "status"]
    if include_contacts:
        headers += ["contact_name", "contact_title", "contact_linkedin", "personal_email", "work_email", "phone", "whatsapp", "potential_contacts", "contact_confidence"]
    sheet.append(headers)
    for lead in leads:
        row = [lead.company_name, lead.website, lead.facebook_url, lead.linkedin_url, lead.country, lead.source, lead.contact_status]
        if include_contacts:
            contact = (CONTACTS.get(str(lead.id)) or [None])[0]
            row += [
                contact.person_name if contact else None,
                contact.title if contact else None,
                contact.linkedin_personal_url if contact else None,
                contact.personal_email if contact else None,
                contact.work_email if contact else None,
                contact.phone if contact else None,
                contact.whatsapp if contact else None,
                str(contact.potential_contacts) if contact else None,
                contact.confidence if contact else None,
            ]
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
