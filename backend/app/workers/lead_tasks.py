import asyncio
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.api.v1.leads import CONTACTS, LEADS
from app.services.contact.pipeline import ContactPipeline
from app.workers.celery_app import celery_app


def _find_lead_by_id(lead_id: str):
    for leads in LEADS.values():
        for lead in leads:
            if str(lead.id) == str(lead_id):
                return lead
    return None


def _update_contact_status(lead_id: str, status: str, error: str | None = None) -> None:
    lead = _find_lead_by_id(lead_id)
    if not lead:
        return
    lead.contact_status = status
    lead.raw_data = {**(lead.raw_data or {}), "contact_error": error}


def _save_contacts(lead_id: str, contacts: list) -> None:
    CONTACTS[str(lead_id)] = contacts
    lead = _find_lead_by_id(lead_id)
    if lead and contacts:
        contact = contacts[0]
        lead.contact_name = contact.person_name
        lead.contact_title = contact.title
        lead.linkedin_personal_url = contact.linkedin_personal_url
        lead.personal_email = contact.personal_email
        lead.work_email = contact.work_email
        lead.phone = contact.phone
        lead.whatsapp = contact.whatsapp
        lead.potential_contacts = contact.potential_contacts


@celery_app.task(
    bind=True,
    name="workers.lead_tasks.enrich_contacts_task",
    time_limit=600,
    soft_time_limit=540,
    max_retries=0,
)
def enrich_contacts_task(self, lead_ids: list[str], enrich_task_id: str):
    for lead_id in lead_ids:
        _update_contact_status(lead_id, "running")
        try:
            lead = _find_lead_by_id(lead_id)
            if not lead:
                _update_contact_status(lead_id, "failed", error="lead not found")
                continue

            pipeline = ContactPipeline()
            result = asyncio.run(pipeline.run(lead))
            if result.core_contacts:
                _save_contacts(lead_id, result.core_contacts)
                _update_contact_status(lead_id, "done")
            else:
                _update_contact_status(lead_id, "no_data")
        except SoftTimeLimitExceeded:
            _update_contact_status(lead_id, "timeout")
        except Exception as exc:
            _update_contact_status(lead_id, "failed", error=str(exc))

    return {"task_id": enrich_task_id, "lead_ids": lead_ids, "status": "completed"}
