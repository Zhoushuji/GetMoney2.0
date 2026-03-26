from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.task import Task
from app.services.workspace_store import get_all_task_leads, get_latest_root_task_id, get_root_task

router = APIRouter(prefix="/outreach", tags=["outreach"])


def _empty_preview(
    task_id: str | None,
    *,
    task_status: str | None = None,
    task_progress: int | None = None,
    next_actions: list[str] | None = None,
) -> dict:
    return {
        "status": "empty",
        "task_id": task_id,
        "task_status": task_status,
        "task_progress": task_progress,
        "summary": {
            "lead_count": 0,
            "contact_count": 0,
            "channel_counts": {"email": 0, "linkedin": 0, "whatsapp": 0, "phone": 0},
        },
        "recommended_channels": [],
        "message_recommendations": [],
        "sample_targets": [],
        "next_actions": next_actions
        or [
            "Run Lead Discovery first to create a lead task.",
            "Use Core Contact Intelligence to enrich people and channel data.",
            "Return here to review deterministic outreach suggestions.",
        ],
        "generated_at": None,
        "contacts_indexed": 0,
    }


def _build_channel_flags(lead: Lead) -> dict[str, bool]:
    return {
        "email": bool(lead.work_email or lead.personal_email),
        "linkedin": bool(lead.linkedin_personal_url or lead.linkedin_url),
        "whatsapp": bool(lead.whatsapp),
        "phone": bool(lead.phone),
    }


def _build_message(channel: str, lead: Lead) -> dict[str, str]:
    company = lead.company_name or "your team"
    contact_name = lead.contact_name or "there"
    title = lead.contact_title or "team"

    if channel == "email":
        return {
            "channel": "email",
            "subject": f"Quick note for {company}",
            "body": (
                f"Hi {contact_name},\n\n"
                f"I reviewed {company} and thought it may be worth a short conversation about how teams in your space are improving sourcing and response speed.\n\n"
                f"If this is relevant, I can send a 2-minute summary tailored to {title}.\n\n"
                "Best,\nYour outreach team"
            ),
        }
    if channel == "linkedin":
        return {
            "channel": "linkedin",
            "subject": "LinkedIn connection note",
            "body": (
                f"Hi {contact_name}, I came across {company} and thought it would be useful to connect. "
                "We help teams compare suppliers, prioritize contact channels, and shorten the first-response cycle."
            ),
        }
    if channel == "whatsapp":
        return {
            "channel": "whatsapp",
            "subject": "Short WhatsApp opener",
            "body": (
                f"Hi {contact_name}, this is a short note for {company}. "
                "I have one practical idea for improving first-touch response and can share it if useful."
            ),
        }
    return {
        "channel": channel,
        "subject": "Call opener",
        "body": (
            f"Hi {contact_name}, I am reaching out regarding {company}. "
            "I have a concise idea for outreach prioritization and would value 2 minutes to see whether it fits your current workflow."
        ),
    }


def _effective_status(task: Task | None) -> str | None:
    if task is None:
        return None
    if task.stopped_early and task.status == "completed":
        return "stopped_early"
    return task.status


async def _contacts_indexed(session: AsyncSession, task_id: UUID) -> int:
    result = await session.execute(
        select(func.count(Contact.id))
        .join(Lead, Lead.id == Contact.lead_id)
        .where(Lead.task_id == task_id)
    )
    return int(result.scalar_one() or 0)


async def _summarize_leads(session: AsyncSession, task_id: UUID | None) -> dict:
    selected_task_id = task_id or await get_latest_root_task_id(session)
    if not selected_task_id:
        return _empty_preview(None)

    root_task = await get_root_task(session, selected_task_id)
    leads = await get_all_task_leads(session, selected_task_id)
    task_status = _effective_status(root_task)
    task_progress = root_task.progress if root_task else None
    if not leads:
        if task_status == "running":
            return _empty_preview(
                str(selected_task_id),
                task_status=task_status,
                task_progress=task_progress,
                next_actions=[
                    "The selected task is still running, so outreach data is not ready yet.",
                    "Refresh in a few seconds after discovery finishes.",
                    "If it stalls, check the discovery task status and logs first.",
                ],
            )
        if task_status == "failed":
            return _empty_preview(
                str(selected_task_id),
                task_status=task_status,
                task_progress=task_progress,
                next_actions=[
                    "The selected task failed before producing outreach data.",
                    "Rerun discovery or contact enrichment, then refresh this preview.",
                    "Check the task error details before trying again.",
                ],
            )
        return _empty_preview(
            str(selected_task_id),
            task_status=task_status,
            task_progress=task_progress,
            next_actions=[
                "No leads were found for the selected task.",
                "Rerun discovery with a broader country or language set.",
                "Check whether the search task has completed successfully.",
            ],
        )

    contactable_lead_count = 0
    contact_count = 0
    channel_counts = {"email": 0, "linkedin": 0, "whatsapp": 0, "phone": 0}
    sample_targets = []

    for lead in leads:
        channels = _build_channel_flags(lead)
        has_contact_signal = bool(
            lead.contact_name
            or lead.contact_title
            or lead.personal_email
            or lead.work_email
            or lead.phone
            or lead.whatsapp
            or lead.linkedin_personal_url
        )
        if has_contact_signal:
            contact_count += 1
        if lead.decision_maker_status == "done":
            contactable_lead_count += 1
        for key, enabled in channels.items():
            if enabled:
                channel_counts[key] += 1
        sample_targets.append(
            {
                "lead_id": str(lead.id),
                "company_name": lead.company_name,
                "contact_name": lead.contact_name,
                "contact_title": lead.contact_title,
                "country": lead.country,
                "channels": [name for name, enabled in channels.items() if enabled],
            }
        )

    sample_targets.sort(
        key=lambda item: (
            -len(item["channels"]),
            -(1 if item["contact_name"] else 0),
            item["company_name"] or item["lead_id"],
        )
    )
    sample_targets = sample_targets[:5]

    ranked_channels = [
        {"channel": "email", "count": channel_counts["email"], "priority": 1, "reason": "Best for direct follow-up when a work or personal email exists."},
        {"channel": "linkedin", "count": channel_counts["linkedin"], "priority": 2, "reason": "Useful when a personal profile is available or email coverage is weak."},
        {"channel": "whatsapp", "count": channel_counts["whatsapp"], "priority": 3, "reason": "Fastest response path for contacts that exposed WhatsApp."},
        {"channel": "phone", "count": channel_counts["phone"], "priority": 4, "reason": "Fallback for teams that only expose a phone number."},
    ]
    recommended_channels = sorted(
        (item for item in ranked_channels if item["count"] > 0),
        key=lambda item: (-item["count"], item["priority"]),
    )

    lead_for_messages = max(
        leads,
        key=lambda lead: (
            sum(1 for enabled in _build_channel_flags(lead).values() if enabled),
            bool(lead.contact_name),
            bool(lead.company_name),
        ),
    )
    active_channels = [name for name in ("email", "linkedin", "whatsapp", "phone") if _build_channel_flags(lead_for_messages).get(name)]
    if not active_channels:
        active_channels = ["email", "linkedin"]

    message_recommendations = [_build_message(channel, lead_for_messages) for channel in active_channels[:3]]
    contacts_indexed = await _contacts_indexed(session, selected_task_id)

    return {
        "status": "ready",
        "task_id": str(selected_task_id),
        "task_status": task_status,
        "task_progress": task_progress,
        "summary": {
            "lead_count": len(leads),
            "contact_count": contact_count,
            "channel_counts": channel_counts,
        },
        "contactable_lead_count": contactable_lead_count,
        "recommended_channels": recommended_channels,
        "message_recommendations": message_recommendations,
        "sample_targets": sample_targets,
        "next_actions": [
            "Start with the highest-coverage channel and keep the first message short.",
            "Personalize the first line using the company name and contact title.",
            "Move high-intent replies into CRM follow-up before sending a second touch.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contacts_indexed": contacts_indexed,
    }


@router.get("/preview")
async def get_outreach_preview(task_id: UUID | None = Query(None), db: AsyncSession = Depends(get_db)) -> dict:
    return await _summarize_leads(db, task_id)
