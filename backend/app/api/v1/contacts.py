import asyncio
from datetime import datetime, timezone
import logging
import traceback
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal, get_db
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.task import Task
from app.schemas.contact import ContactEnrichAllRequest, ContactEnrichRequest, ContactListResponse, ContactRead, ContactStatusResponse
from app.schemas.task import TaskCreateResponse
from app.services.contact.intelligence import ContactIntelligenceService
from app.services.workspace_store import CONTACT_TASK_TYPE, get_contact_list, get_lead_with_contacts

router = APIRouter(prefix="/contacts", tags=["contacts"])
logger = logging.getLogger(__name__)
DECISION_PROVENANCE_FIELDS = ("contact_name", "contact_title", "linkedin_personal_url", "personal_email", "work_email")
GENERAL_PROVENANCE_FIELDS = ("phone", "whatsapp", "potential_contacts")


def _update_lead_contact_status(lead: Lead, status: str, error: str | None = None) -> None:
    lead.contact_status = status
    lead.raw_data = {**(lead.raw_data or {}), "contact_error": error}


def _set_dual_status(lead: Lead, decision_status: str, general_status: str, error: str | None = None, error_details: dict | None = None) -> None:
    lead.decision_maker_status = decision_status
    lead.general_contact_status = general_status
    lead.contact_status = "done" if decision_status == "done" or general_status == "done" else decision_status
    lead.raw_data = {
        **(lead.raw_data or {}),
        "contact_error": error,
        "contact_error_details": error_details,
    }


def _build_error_details(exc: Exception | None, lead: Lead | None) -> dict | None:
    if exc is None:
        return None
    details = {
        "type": exc.__class__.__name__,
        "message": str(exc),
        "website": getattr(lead, "website", None),
        "company_name": getattr(lead, "company_name", None),
        "traceback": "".join(traceback.format_exception(exc)).strip(),
    }
    exc_details = getattr(exc, "details", None)
    if isinstance(exc_details, dict):
        details.update(exc_details)
    return details


def _status_from_exception(exc: Exception | None, has_data: bool) -> str:
    if has_data:
        return "done"
    if exc is None:
        return "no_data"
    explicit_status = getattr(exc, "status", None)
    if explicit_status == "timeout" or isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    if explicit_status in {"login_wall", "captcha_or_block", "selector_miss", "failed"}:
        return "failed"
    return "failed"


def _clear_decision_summary(lead: Lead) -> None:
    lead.contact_name = None
    lead.contact_title = None
    lead.linkedin_personal_url = None
    lead.personal_email = None
    lead.work_email = None
    raw_data = dict(lead.raw_data or {})
    field_provenance = dict(raw_data.get("field_provenance") or {})
    for field_key in DECISION_PROVENANCE_FIELDS:
        field_provenance.pop(field_key, None)
    raw_data["field_provenance"] = field_provenance
    lead.raw_data = raw_data


def _clear_general_summary(lead: Lead) -> None:
    lead.phone = None
    lead.whatsapp = None
    lead.general_emails = []
    lead.potential_contacts = None
    raw_data = dict(lead.raw_data or {})
    field_provenance = dict(raw_data.get("field_provenance") or {})
    for field_key in GENERAL_PROVENANCE_FIELDS:
        field_provenance.pop(field_key, None)
    raw_data["field_provenance"] = field_provenance
    lead.raw_data = raw_data


async def _mark_contact_task(task_id: UUID, *, status: str | None = None, completed: int | None = None, progress: int | None = None, phase: str | None = None) -> None:
    async with SessionLocal() as session:
        task = await session.get(Task, task_id)
        if not task:
            return
        if status is not None:
            task.status = status
        if completed is not None:
            task.completed = completed
        if progress is not None:
            task.progress = progress
        if phase is not None:
            task.phase = phase
        task.updated_at = datetime.now(timezone.utc)
        if task.status == "completed":
            task.estimated_remaining_seconds = 0
        await session.commit()


async def _persist_enrichment_result(
    lead_id: UUID,
    *,
    mode: str,
    decision_contacts,
    potential_contacts: dict | None,
    decision_exc: Exception | None,
    general_exc: Exception | None,
) -> None:
    async with SessionLocal() as session:
        lead = await session.get(Lead, lead_id)
        if lead is None:
            return

        if mode in {"all", "decision_maker"}:
            await session.execute(delete(Contact).where(Contact.lead_id == lead_id))
            _clear_decision_summary(lead)
        if mode in {"all", "general_contact"}:
            _clear_general_summary(lead)

        decision_status = lead.decision_maker_status if mode == "general_contact" else _status_from_exception(decision_exc, bool(decision_contacts))

        has_general = bool(
            potential_contacts
            and (
                potential_contacts.get("phones")
                or potential_contacts.get("whatsapp")
                or potential_contacts.get("generic_emails")
                or potential_contacts.get("emails")
            )
        )
        general_status = lead.general_contact_status if mode == "decision_maker" else _status_from_exception(general_exc, has_general)

        if decision_contacts:
            persisted = []
            for contact in decision_contacts:
                payload = contact.model_dump()
                payload["lead_id"] = lead_id
                persisted.append(Contact(**payload))
            session.add_all(persisted)
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
        raw_data = dict(lead.raw_data or {})
        field_provenance = dict(raw_data.get("field_provenance") or {})
        if decision_contacts:
            best = decision_contacts[0]
            decision_source_url = next((item for item in (best.source_urls or []) if item), None) or best.linkedin_personal_url
            source_hint = best.linkedin_personal_url or decision_source_url
            field_provenance.update(
                {
                    "contact_name": {
                        "source_type": "decision_maker",
                        "source_url": decision_source_url,
                        "extractor": "decision_maker_enrichment",
                        "source_hint": source_hint,
                    },
                    "contact_title": {
                        "source_type": "decision_maker",
                        "source_url": decision_source_url,
                        "extractor": "decision_maker_enrichment",
                        "source_hint": source_hint,
                    },
                    "linkedin_personal_url": {
                        "source_type": "decision_maker",
                        "source_url": best.linkedin_personal_url or decision_source_url,
                        "extractor": "decision_maker_enrichment",
                        "source_hint": best.title,
                    } if best.linkedin_personal_url or decision_source_url else None,
                    "personal_email": {
                        "source_type": "decision_maker",
                        "source_url": decision_source_url,
                        "extractor": "decision_maker_enrichment",
                        "source_hint": best.personal_email,
                    } if best.personal_email else None,
                    "work_email": {
                        "source_type": "decision_maker",
                        "source_url": decision_source_url,
                        "extractor": "decision_maker_enrichment",
                        "source_hint": best.work_email,
                    } if best.work_email else None,
                }
            )
        if potential_contacts:
            potential_source_url = next((item for item in potential_contacts.get("source_urls", []) if item), None) or lead.website
            if lead.phone:
                field_provenance["phone"] = {
                    "source_type": "potential_contacts",
                    "source_url": potential_source_url,
                    "extractor": "potential_contacts_scan",
                    "source_hint": lead.phone,
                }
            if lead.whatsapp:
                field_provenance["whatsapp"] = {
                    "source_type": "potential_contacts",
                    "source_url": potential_source_url,
                    "extractor": "potential_contacts_scan",
                    "source_hint": lead.whatsapp,
                }
            if lead.potential_contacts:
                field_provenance["potential_contacts"] = {
                    "source_type": "potential_contacts",
                    "source_url": potential_source_url,
                    "extractor": "potential_contacts_scan",
                    "source_hint": ", ".join((lead.potential_contacts or {}).get("items", [])[:3]),
                }
        lead.raw_data = {
            **raw_data,
            "last_contact_mode": mode,
            "field_provenance": {key: value for key, value in field_provenance.items() if value},
        }
        await session.commit()


async def _enrich_one_lead(lead_id: UUID, mode: str = "all", service: ContactIntelligenceService | None = None) -> None:
    async with SessionLocal() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            return
        _set_dual_status(
            lead,
            "running" if mode in {"all", "decision_maker"} else lead.decision_maker_status,
            "running" if mode in {"all", "general_contact"} else lead.general_contact_status,
        )
        await session.commit()
        lead_snapshot = lead

    service = service or ContactIntelligenceService()
    decision_exc: Exception | None = None
    general_exc: Exception | None = None
    decision_contacts: list = []
    potential_contacts: dict | None = None

    if mode in {"all", "decision_maker"}:
        try:
            decision_contacts = await asyncio.wait_for(service.find_decision_makers(lead_snapshot), timeout=60)
        except asyncio.TimeoutError as exc:
            decision_exc = exc
            logger.warning(
                "decision_maker_timeout lead_id=%s website=%s company_name=%s exception_type=%s exception_message=%s traceback=%s",
                lead_id, lead_snapshot.website, lead_snapshot.company_name, type(exc).__name__, str(exc), traceback.format_exc(limit=20),
            )
        except Exception as exc:
            decision_exc = exc
            logger.exception(
                "decision_maker_failed lead_id=%s website=%s company_name=%s exception_type=%s exception_message=%s traceback=%s",
                lead_id, lead_snapshot.website, lead_snapshot.company_name, type(exc).__name__, str(exc), traceback.format_exc(limit=30),
            )

    if mode in {"all", "general_contact"}:
        try:
            potential_contacts = await asyncio.wait_for(service.find_potential_contacts(lead_snapshot), timeout=60)
        except asyncio.TimeoutError as exc:
            general_exc = exc
            logger.warning(
                "general_contact_timeout lead_id=%s website=%s company_name=%s exception_type=%s exception_message=%s traceback=%s",
                lead_id, lead_snapshot.website, lead_snapshot.company_name, type(exc).__name__, str(exc), traceback.format_exc(limit=20),
            )
        except Exception as exc:
            general_exc = exc
            logger.exception(
                "general_contact_failed lead_id=%s website=%s company_name=%s exception_type=%s exception_message=%s traceback=%s",
                lead_id, lead_snapshot.website, lead_snapshot.company_name, type(exc).__name__, str(exc), traceback.format_exc(limit=30),
            )

    await _persist_enrichment_result(
        lead_id,
        mode=mode,
        decision_contacts=decision_contacts,
        potential_contacts=potential_contacts,
        decision_exc=decision_exc,
        general_exc=general_exc,
    )


async def _run_enrichment_batch(task_id: UUID, lead_ids: list[UUID], mode: str = "all") -> None:
    if not lead_ids:
        await _mark_contact_task(task_id, status="completed", completed=0, progress=100, phase="completed")
        return
    await _mark_contact_task(task_id, status="running", phase="running", progress=0, completed=0)
    service = ContactIntelligenceService()
    for idx, lead_id in enumerate(lead_ids, start=1):
        await _enrich_one_lead(lead_id, mode=mode, service=service)
        await _mark_contact_task(task_id, completed=idx, progress=int((idx / max(1, len(lead_ids))) * 100), phase="running")
    await _mark_contact_task(task_id, status="completed", completed=len(lead_ids), progress=100, phase="completed")


@router.post("/enrich", response_model=TaskCreateResponse)
async def enrich_contacts(payload: ContactEnrichRequest, db: AsyncSession = Depends(get_db)) -> TaskCreateResponse:
    result = await db.execute(select(Lead).where(Lead.id.in_(payload.lead_ids)))
    leads = result.scalars().all()
    lead_ids = [lead.id for lead in leads]
    parent_task_id = leads[0].task_id if leads else None
    if parent_task_id and any(lead.task_id != parent_task_id for lead in leads):
        raise HTTPException(status_code=400, detail="All lead_ids must belong to the same lead search task")

    now = datetime.now(timezone.utc)
    task = Task(
        parent_task_id=parent_task_id,
        type=CONTACT_TASK_TYPE,
        status="pending",
        progress=0,
        total=len(lead_ids),
        completed=0,
        target_count=len(lead_ids),
        confirmed_leads=0,
        stopped_early=False,
        params={"mode": payload.mode, "lead_ids_count": len(lead_ids)},
        phase="queued",
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    asyncio.create_task(_run_enrichment_batch(task.id, lead_ids, mode=payload.mode))
    return TaskCreateResponse(task_id=task.id)


@router.post("/enrich/all", response_model=TaskCreateResponse)
async def enrich_all_contacts(payload: ContactEnrichAllRequest, db: AsyncSession = Depends(get_db)) -> TaskCreateResponse:
    result = await db.execute(
        select(Lead.id).where(
            Lead.task_id == payload.task_id,
            (
                Lead.decision_maker_status.in_(("pending", "failed", "timeout", "no_data"))
                | Lead.general_contact_status.in_(("pending", "failed", "timeout", "no_data"))
            ),
        )
    )
    lead_ids = list(result.scalars().all())
    return await enrich_contacts(ContactEnrichRequest(lead_ids=lead_ids), db)


@router.get("", response_model=ContactListResponse)
async def list_contacts(lead_id: UUID, db: AsyncSession = Depends(get_db)) -> ContactListResponse:
    return ContactListResponse(contacts=await get_contact_list(db, lead_id))


@router.get("/status/{lead_id}", response_model=ContactStatusResponse)
async def get_contact_status(lead_id: UUID, db: AsyncSession = Depends(get_db)) -> ContactStatusResponse:
    lead = await get_lead_with_contacts(db, lead_id)
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
        decision_maker_status=lead.decision_maker_status,
        general_contact_status=lead.general_contact_status,
        contacts=[ContactRead.model_validate(contact) for contact in lead.contacts],
        potential_contacts={
            "phone": lead.phone,
            "whatsapp": lead.whatsapp,
            "general_emails": lead.general_emails or [],
            "items": (lead.potential_contacts or {}).get("items", []),
        },
        error=error,
        error_details=raw_data.get("contact_error_details"),
    )
