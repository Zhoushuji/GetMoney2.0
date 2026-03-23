from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import APIRouter

from app.api.v1.leads import CONTACTS, LEADS, TASKS
from app.schemas.contact import ContactEnrichAllRequest, ContactEnrichRequest, ContactListResponse, ContactRead
from app.schemas.task import TaskCreateResponse

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _build_contact(lead) -> ContactRead:
    now = datetime.now(timezone.utc)
    website_host = urlparse(lead.website or "").netloc.removeprefix("www.")
    domain = website_host or "example.com"
    company_tokens = (lead.company_name or "Business Contact").split()
    person_name = f"{company_tokens[0]} Contact"
    return ContactRead(
        id=uuid4(),
        lead_id=lead.id,
        person_name=person_name,
        title="Managing Director",
        priority=1,
        personal_email=f"{company_tokens[0].lower()}@gmail.com" if company_tokens else None,
        work_email=f"contact@{domain}" if domain else None,
        linkedin_personal_url=f"https://www.linkedin.com/in/{company_tokens[0].lower()}-contact" if company_tokens else None,
        phone="+971 50 555 0101",
        whatsapp="+971 50 555 0101",
        potential_contacts={"assistant": f"hello@{domain}"},
        source_urls=[lead.website] if lead.website else [],
        verified_at=now,
    )


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
        "confirmed_leads": len(payload.lead_ids),
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
        contact = _build_contact(lead)
        CONTACTS[str(lead_id)] = [contact]
        lead.contact_status = "done"
        lead.contact_name = contact.person_name
        lead.contact_title = contact.title
        lead.linkedin_personal_url = contact.linkedin_personal_url
        lead.personal_email = contact.personal_email
        lead.work_email = contact.work_email
        lead.phone = contact.phone
        lead.whatsapp = contact.whatsapp
        lead.potential_contacts = contact.potential_contacts
    return TaskCreateResponse(task_id=task_id)


@router.post("/enrich/all", response_model=TaskCreateResponse)
async def enrich_all_contacts(payload: ContactEnrichAllRequest) -> TaskCreateResponse:
    lead_ids = [lead.id for lead in LEADS.get(str(payload.task_id), []) if lead.contact_status == "pending"]
    return await enrich_contacts(ContactEnrichRequest(lead_ids=lead_ids))


@router.get("", response_model=ContactListResponse)
async def list_contacts(lead_id: UUID) -> ContactListResponse:
    return ContactListResponse(contacts=CONTACTS.get(str(lead_id), []))
