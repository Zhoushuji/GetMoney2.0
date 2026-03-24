from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter

from app.api.v1.leads import CONTACTS, LEADS, TASKS
from app.schemas.contact import ContactEnrichAllRequest, ContactEnrichRequest, ContactListResponse, ContactStatusResponse
from app.schemas.task import TaskCreateResponse
from app.workers.lead_tasks import enrich_contacts_task

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _find_lead(lead_id: str):
    for leads in LEADS.values():
        for lead in leads:
            if str(lead.id) == lead_id:
                return lead
    return None


def _update_lead_contact_status(lead, status: str, error: str | None = None) -> None:
    lead.contact_status = status
    lead.raw_data = {**(lead.raw_data or {}), "contact_error": error}


@router.post("/enrich", response_model=TaskCreateResponse)
async def enrich_contacts(payload: ContactEnrichRequest) -> TaskCreateResponse:
    task_id = uuid4()
    now = datetime.now(timezone.utc)
    TASKS[str(task_id)] = {
        "id": task_id,
        "status": "pending",
        "progress": 0,
        "total": len(payload.lead_ids),
        "completed": 0,
        "confirmed_leads": 0,
        "target_count": len(payload.lead_ids),
        "stopped_early": False,
        "created_at": now,
        "updated_at": now,
    }

    lead_lookup = {str(lead.id): lead for leads in LEADS.values() for lead in leads}
    lead_ids: list[str] = []
    for lead_id in payload.lead_ids:
        lead = lead_lookup.get(str(lead_id))
        if not lead:
            continue
        _update_lead_contact_status(lead, "pending")
        lead_ids.append(str(lead_id))

    enrich_contacts_task.delay(lead_ids=lead_ids, enrich_task_id=str(task_id))
    return TaskCreateResponse(task_id=task_id)


@router.post("/enrich/all", response_model=TaskCreateResponse)
async def enrich_all_contacts(payload: ContactEnrichAllRequest) -> TaskCreateResponse:
    lead_ids = [lead.id for lead in LEADS.get(str(payload.task_id), []) if lead.contact_status in {"pending", "failed", "timeout", "no_data"}]
    return await enrich_contacts(ContactEnrichRequest(lead_ids=lead_ids))


@router.get("", response_model=ContactListResponse)
async def list_contacts(lead_id: UUID) -> ContactListResponse:
    return ContactListResponse(contacts=CONTACTS.get(str(lead_id), []))


@router.get("/status/{lead_id}", response_model=ContactStatusResponse)
async def get_contact_status(lead_id: UUID) -> ContactStatusResponse:
    lead = _find_lead(str(lead_id))
    if not lead:
        return ContactStatusResponse(lead_id=lead_id, contact_status="failed", contacts=[], error="Lead not found")
    return ContactStatusResponse(
        lead_id=lead_id,
        contact_status=lead.contact_status,
        contacts=CONTACTS.get(str(lead_id), []) if lead.contact_status == "done" else [],
        error=(lead.raw_data or {}).get("contact_error"),
    )
