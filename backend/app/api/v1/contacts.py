from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter

from app.api.v1.leads import CONTACTS, LEADS, TASKS
from app.schemas.contact import ContactEnrichAllRequest, ContactEnrichRequest, ContactListResponse, ContactRead
from app.schemas.task import TaskCreateResponse

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("/enrich", response_model=TaskCreateResponse)
async def enrich_contacts(payload: ContactEnrichRequest) -> TaskCreateResponse:
    task_id = uuid4()
    now = datetime.now(timezone.utc)
    TASKS[str(task_id)] = {"id": task_id, "status": "completed", "progress": 100, "total": len(payload.lead_ids), "completed": len(payload.lead_ids), "created_at": now, "updated_at": now}
    for lead_id in payload.lead_ids:
        CONTACTS[str(lead_id)] = [
            ContactRead(
                id=uuid4(),
                lead_id=lead_id,
                person_name="Alex Morgan",
                title="Managing Director",
                priority=2,
                personal_email="alex.morgan@example.com",
                work_email="amorgan@example.com",
                linkedin_personal_url="https://linkedin.com/in/alex-morgan",
                phone="+1 202-555-0182",
                whatsapp="+1 202-555-0182",
                potential_contacts={"alternate_email": "alex@example.com"},
                source_urls=["https://example.com/about", "https://linkedin.com/in/alex-morgan"],
                verified_at=now,
            )
        ]
    return TaskCreateResponse(task_id=task_id)


@router.post("/enrich/all", response_model=TaskCreateResponse)
async def enrich_all_contacts(payload: ContactEnrichAllRequest) -> TaskCreateResponse:
    lead_ids = [lead.id for lead in LEADS.get(str(payload.task_id), [])]
    return await enrich_contacts(ContactEnrichRequest(lead_ids=lead_ids))


@router.get("", response_model=ContactListResponse)
async def list_contacts(lead_id: UUID) -> ContactListResponse:
    return ContactListResponse(contacts=CONTACTS.get(str(lead_id), []))
