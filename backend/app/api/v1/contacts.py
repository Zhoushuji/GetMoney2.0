import asyncio
from datetime import datetime, timezone
import logging
import traceback
from uuid import UUID, uuid4

from fastapi import APIRouter

from app.api.v1.leads import CONTACTS, LEADS, TASKS
from app.schemas.contact import ContactEnrichAllRequest, ContactEnrichRequest, ContactListResponse, ContactStatusResponse
from app.schemas.task import TaskCreateResponse
from app.services.contact.intelligence import ContactIntelligenceService

router = APIRouter(prefix="/contacts", tags=["contacts"])
logger = logging.getLogger(__name__)


def _find_lead(lead_id: str):
    for leads in LEADS.values():
        for lead in leads:
            if str(lead.id) == lead_id:
                return lead
    return None


def _update_lead_contact_status(lead, status: str, error: str | None = None) -> None:
    lead.contact_status = status
    lead.raw_data = {**(lead.raw_data or {}), "contact_error": error}


def _set_dual_status(lead, decision_status: str, general_status: str, error: str | None = None, error_details: dict | None = None) -> None:
    lead.decision_maker_status = decision_status
    lead.general_contact_status = general_status
    lead.contact_status = "done" if decision_status == "done" or general_status == "done" else decision_status
    lead.raw_data = {
        **(lead.raw_data or {}),
        "contact_error": error,
        "contact_error_details": error_details,
    }


def _build_error_details(exc: Exception | None, lead) -> dict | None:
    if exc is None:
        return None
    return {
        "type": exc.__class__.__name__,
        "message": str(exc),
        "website": getattr(lead, "website", None),
        "company_name": getattr(lead, "company_name", None),
        "traceback": traceback.format_exc(limit=30),
    }


async def _enrich_one_lead(lead_id: str, mode: str = "all") -> None:
    lead = _find_lead(lead_id)
    if not lead:
        return
    _set_dual_status(
        lead,
        "running" if mode in {"all", "decision_maker"} else getattr(lead, "decision_maker_status", "pending"),
        "running" if mode in {"all", "general_contact"} else getattr(lead, "general_contact_status", "pending"),
    )
    service = ContactIntelligenceService()

    decision_exc: Exception | None = None
    general_exc: Exception | None = None

    decision_contacts: list = []
    potential_contacts: dict | None = None

    if mode in {"all", "decision_maker"}:
        try:
            decision_contacts = await asyncio.wait_for(service.find_decision_makers(lead), timeout=60)
        except asyncio.TimeoutError as exc:
            decision_exc = exc
            logger.warning(
                "decision_maker_timeout lead_id=%s website=%s company_name=%s exception_type=%s exception_message=%s traceback=%s",
                lead_id, lead.website, lead.company_name, type(exc).__name__, str(exc), traceback.format_exc(limit=20),
            )
        except Exception as exc:
            decision_exc = exc
            logger.exception(
                "decision_maker_failed lead_id=%s website=%s company_name=%s exception_type=%s exception_message=%s traceback=%s",
                lead_id, lead.website, lead.company_name, type(exc).__name__, str(exc), traceback.format_exc(limit=30),
            )

    if mode in {"all", "general_contact"}:
        try:
            potential_contacts = await asyncio.wait_for(service.find_potential_contacts(lead), timeout=60)
        except asyncio.TimeoutError as exc:
            general_exc = exc
            logger.warning(
                "general_contact_timeout lead_id=%s website=%s company_name=%s exception_type=%s exception_message=%s traceback=%s",
                lead_id, lead.website, lead.company_name, type(exc).__name__, str(exc), traceback.format_exc(limit=20),
            )
        except Exception as exc:
            general_exc = exc
            logger.exception(
                "general_contact_failed lead_id=%s website=%s company_name=%s exception_type=%s exception_message=%s traceback=%s",
                lead_id, lead.website, lead.company_name, type(exc).__name__, str(exc), traceback.format_exc(limit=30),
            )

    decision_status = getattr(lead, "decision_maker_status", "pending") if mode == "general_contact" else ("failed" if decision_exc else ("done" if decision_contacts else "no_data"))
    if isinstance(decision_exc, asyncio.TimeoutError):
        decision_status = "timeout"

    has_general = bool(
        potential_contacts
        and (
            potential_contacts.get("phones")
            or potential_contacts.get("whatsapp")
            or potential_contacts.get("generic_emails")
            or potential_contacts.get("emails")
        )
    )
    general_status = getattr(lead, "general_contact_status", "pending") if mode == "decision_maker" else ("failed" if general_exc else ("done" if has_general else "no_data"))
    if isinstance(general_exc, asyncio.TimeoutError):
        general_status = "timeout"

    if decision_contacts:
        CONTACTS[str(lead.id)] = decision_contacts
        best = decision_contacts[0]
        lead.contact_name = best.person_name
        lead.contact_title = best.title
        lead.linkedin_personal_url = best.linkedin_personal_url
        lead.personal_email = best.personal_email
        lead.work_email = best.work_email
    if potential_contacts:
        lead.phone = next(iter(potential_contacts.get("phones", [])), None)
        lead.whatsapp = next(iter(potential_contacts.get("whatsapp", [])), None)
        lead.general_emails = potential_contacts.get("generic_emails", [])
        lead.potential_contacts = {"items": potential_contacts.get("all", [])} if potential_contacts.get("all") else None

    error_exc = decision_exc or general_exc
    _set_dual_status(lead, decision_status, general_status, error=str(error_exc) if error_exc else None, error_details=_build_error_details(error_exc, lead))


async def _run_enrichment_batch(task_id: str, lead_ids: list[str], mode: str = "all") -> None:
    task = TASKS.get(task_id)
    if not task:
        return
    task["status"] = "running"
    for idx, lead_id in enumerate(lead_ids, start=1):
        await _enrich_one_lead(lead_id, mode=mode)
        task["completed"] = idx
        task["progress"] = int((idx / max(1, len(lead_ids))) * 100)
        task["updated_at"] = datetime.now(timezone.utc)
    task["status"] = "completed"
    task["progress"] = 100
    task["updated_at"] = datetime.now(timezone.utc)


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
        _set_dual_status(lead, "pending", "pending")
        lead_ids.append(str(lead_id))

    try:
        asyncio.create_task(_run_enrichment_batch(str(task_id), lead_ids, mode=payload.mode))
    except asyncio.TimeoutError as exc:
        logger.warning(
            "contacts_enrich_dispatch_timeout lead_ids=%s exception_type=%s exception_message=%s traceback=%s",
            lead_ids,
            type(exc).__name__,
            str(exc),
            traceback.format_exc(limit=20),
        )
    except Exception as exc:
        for lead_id in lead_ids:
            lead = lead_lookup.get(lead_id)
            if not lead:
                continue
            _set_dual_status(lead, "failed", "failed", error=str(exc), error_details=_build_error_details(exc, lead))
            logger.exception(
                "contacts_enrich_dispatch_failed lead_id=%s website=%s company_name=%s exception_type=%s exception_message=%s traceback=%s",
                lead_id,
                getattr(lead, "website", None),
                getattr(lead, "company_name", None),
                type(exc).__name__,
                str(exc),
                traceback.format_exc(limit=30),
            )
    return TaskCreateResponse(task_id=task_id)


@router.post("/enrich/all", response_model=TaskCreateResponse)
async def enrich_all_contacts(payload: ContactEnrichAllRequest) -> TaskCreateResponse:
    lead_ids = [lead.id for lead in LEADS.get(str(payload.task_id), []) if lead.decision_maker_status in {"pending", "failed", "timeout", "no_data"} or lead.general_contact_status in {"pending", "failed", "timeout", "no_data"}]
    return await enrich_contacts(ContactEnrichRequest(lead_ids=lead_ids))


@router.get("", response_model=ContactListResponse)
async def list_contacts(lead_id: UUID) -> ContactListResponse:
    return ContactListResponse(contacts=CONTACTS.get(str(lead_id), []))


@router.get("/status/{lead_id}", response_model=ContactStatusResponse)
async def get_contact_status(lead_id: UUID) -> ContactStatusResponse:
    lead = _find_lead(str(lead_id))
    if not lead:
        return ContactStatusResponse(
            lead_id=lead_id,
            decision_maker_status="failed",
            general_contact_status="failed",
            contacts=[],
            potential_contacts=None,
            error="Lead not found",
            error_details={"type": "NotFound", "message": "Lead not found", "website": None, "company_name": None},
        )
    raw_data = lead.raw_data or {}
    error = raw_data.get("contact_error")
    return ContactStatusResponse(
        lead_id=lead_id,
        decision_maker_status=getattr(lead, "decision_maker_status", lead.contact_status),
        general_contact_status=getattr(lead, "general_contact_status", lead.contact_status),
        contacts=CONTACTS.get(str(lead_id), []),
        potential_contacts={
            "phone": getattr(lead, "phone", None),
            "whatsapp": getattr(lead, "whatsapp", None),
            "general_emails": getattr(lead, "general_emails", None),
            "items": (getattr(lead, "potential_contacts", None) or {}).get("items", []),
        },
        error=error,
        error_details=raw_data.get("contact_error_details"),
    )
