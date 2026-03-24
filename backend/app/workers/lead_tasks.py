import asyncio
import logging
import traceback
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.api.v1.leads import CONTACTS, LEADS
from app.services.contact.pipeline import ContactPipeline
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


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


def _save_potential_contacts(lead_id: str, potential_contacts: list[dict]) -> None:
    lead = _find_lead_by_id(lead_id)
    if not lead:
        return
    items = [f"{item.get('type')}:{item.get('value')}" for item in potential_contacts if item.get("type") and item.get("value")]
    lead.potential_contacts = {"items": sorted(set(items))} if items else None


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
        lead = None
        try:
            lead = _find_lead_by_id(lead_id)
            if not lead:
                _update_contact_status(lead_id, "failed", error="lead not found")
                continue

            pipeline = ContactPipeline()
            result = asyncio.run(pipeline.run(lead))
            if result.errors:
                logger.error(
                    "contact_enrichment_pipeline_errors lead_id=%s website=%s errors=%s",
                    lead_id,
                    getattr(lead, "website", None),
                    result.errors,
                )
            if result.core_contacts:
                _save_contacts(lead_id, result.core_contacts)
                _update_contact_status(lead_id, "done")
            elif result.potential_contacts:
                _save_potential_contacts(lead_id, result.potential_contacts)
                _update_contact_status(lead_id, "no_data")
            else:
                _update_contact_status(lead_id, "no_data")
        except SoftTimeLimitExceeded:
            logger.warning("contact enrichment timeout: lead_id=%s website=%s", lead_id, getattr(lead, "website", None))
            _update_contact_status(lead_id, "timeout")
        except Exception as exc:
            exception_message = f"{type(exc).__name__}: {exc}"
            traceback_text = traceback.format_exc(limit=30)
            logger.exception(
                "contact enrichment failed: lead_id=%s website=%s exception_type=%s exception_message=%s traceback=%s",
                lead_id,
                getattr(lead, "website", None),
                type(exc).__name__,
                str(exc),
                traceback_text,
            )
            _update_contact_status(lead_id, "failed", error=exception_message)
            if lead:
                lead.raw_data = {**(lead.raw_data or {}), "contact_traceback": traceback_text}

    return {"task_id": enrich_task_id, "lead_ids": lead_ids, "status": "completed"}
