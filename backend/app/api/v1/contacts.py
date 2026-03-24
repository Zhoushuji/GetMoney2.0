import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter

from app.api.v1.leads import CONTACTS, LEADS, TASKS
from app.schemas.contact import ContactEnrichAllRequest, ContactEnrichRequest, ContactListResponse
from app.schemas.task import TaskCreateResponse
from app.services.contact.intelligence import ContactIntelligenceService

router = APIRouter(prefix="/contacts", tags=["contacts"])
service = ContactIntelligenceService()


def _update_lead_contact_status(lead, status: str, contact=None) -> None:
    lead.contact_status = status
    lead.contact_name = contact.person_name if contact else None
    lead.contact_title = contact.title if contact else None
    lead.linkedin_personal_url = contact.linkedin_personal_url if contact else None
    lead.personal_email = contact.personal_email if contact else None
    lead.work_email = contact.work_email if contact else None
    lead.phone = contact.phone if contact else None
    lead.whatsapp = contact.whatsapp if contact else None
    lead.potential_contacts = contact.potential_contacts if contact else None


@router.post("/enrich", response_model=TaskCreateResponse)
async def enrich_contacts(payload: ContactEnrichRequest) -> TaskCreateResponse:
    task_id = uuid4()
    now = datetime.now(timezone.utc)
    TASKS[str(task_id)] = {
        "id": task_id,
        "status": "completed",
        "progress": 100,
        "total": len(payload.lead_ids),
        "completed": len(payload.lead_ids),
        "confirmed_leads": 0,
        "target_count": len(payload.lead_ids),
        "stopped_early": False,
        "created_at": now,
        "updated_at": now,
    }
    lead_lookup = {str(lead.id): lead for leads in LEADS.values() for lead in leads}

    for lead_id in payload.lead_ids:
        lead = lead_lookup.get(str(lead_id))
        if not lead:
            continue
        try:
            contacts = await asyncio.wait_for(service.find_contacts(lead), timeout=120)
            CONTACTS[str(lead_id)] = contacts
            contact = contacts[0] if contacts else None
            if contact:
                _update_lead_contact_status(lead, "done", contact=contact)
            else:
                _update_lead_contact_status(lead, "no_data")
        except asyncio.TimeoutError:
            CONTACTS[str(lead_id)] = []
            _update_lead_contact_status(lead, "timeout")
        except Exception:
            CONTACTS[str(lead_id)] = []
            _update_lead_contact_status(lead, "failed")

    return TaskCreateResponse(task_id=task_id)


@router.post("/enrich/all", response_model=TaskCreateResponse)
async def enrich_all_contacts(payload: ContactEnrichAllRequest) -> TaskCreateResponse:
    lead_ids = [lead.id for lead in LEADS.get(str(payload.task_id), []) if lead.contact_status in {"pending", "failed", "timeout"}]
    return await enrich_contacts(ContactEnrichRequest(lead_ids=lead_ids))


@router.get("", response_model=ContactListResponse)
async def list_contacts(lead_id: UUID) -> ContactListResponse:
    return ContactListResponse(contacts=CONTACTS.get(str(lead_id), []))
