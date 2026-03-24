import asyncio

from celery.exceptions import SoftTimeLimitExceeded

from app.api.v1.leads import CONTACTS, LEADS
from app.services.contact.intelligence import ContactIntelligenceService
from app.workers.celery_app import celery_app

service = ContactIntelligenceService()


def _find_lead_by_id(lead_id: str):
    for leads in LEADS.values():
        for lead in leads:
            if str(lead.id) == lead_id:
                return lead
    return None


def _update_lead_contact_status(lead_id: str, status: str) -> None:
    lead = _find_lead_by_id(lead_id)
    if lead:
        lead.contact_status = status


def _save_contacts(lead_id: str, contacts) -> None:
    CONTACTS[str(lead_id)] = contacts


@celery_app.task(bind=True, time_limit=120, soft_time_limit=100, name="workers.contact_tasks.enrich_single_lead")
def enrich_single_lead(self, lead_id: str):
    lead = _find_lead_by_id(lead_id)
    if not lead:
        _update_lead_contact_status(lead_id, "failed")
        return {"lead_id": lead_id, "status": "failed", "error": "lead not found"}

    _update_lead_contact_status(lead_id, "running")
    try:
        contacts = asyncio.run(service.find_contacts(lead))
        if not contacts:
            _update_lead_contact_status(lead_id, "no_data")
            return {"lead_id": lead_id, "status": "no_data"}

        _save_contacts(lead_id, contacts)
        contact = contacts[0]
        lead.contact_name = contact.person_name
        lead.contact_title = contact.title
        lead.linkedin_personal_url = contact.linkedin_personal_url
        lead.personal_email = contact.personal_email
        lead.work_email = contact.work_email
        lead.phone = contact.phone
        lead.whatsapp = contact.whatsapp
        lead.potential_contacts = contact.potential_contacts
        _update_lead_contact_status(lead_id, "done")
        return {"lead_id": lead_id, "status": "done"}
    except SoftTimeLimitExceeded:
        _update_lead_contact_status(lead_id, "timeout")
        return {"lead_id": lead_id, "status": "timeout"}
    except Exception as exc:
        _update_lead_contact_status(lead_id, "failed")
        return {"lead_id": lead_id, "status": "failed", "error": str(exc)}
