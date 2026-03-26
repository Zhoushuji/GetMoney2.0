from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.v1.leads import CONTACTS, LEADS, TASKS

router = APIRouter(prefix="/outreach", tags=["outreach"])


def _task_sort_key(task: dict) -> datetime:
    value = task.get("updated_at") or task.get("created_at")
    if isinstance(value, datetime):
        return value
    return datetime.min.replace(tzinfo=timezone.utc)


def _latest_task_id() -> str | None:
    lead_task_ids = [task_id for task_id in LEADS if task_id in TASKS]
    if lead_task_ids:
        latest_task_id = max(lead_task_ids, key=lambda task_id: _task_sort_key(TASKS[task_id]))
        return str(TASKS[latest_task_id]["id"])
    if not TASKS:
        return None
    latest_task = max(TASKS.values(), key=_task_sort_key)
    return str(latest_task["id"])


def _normalize_task_id(task_id: str | None) -> str | None:
    if not task_id:
        return None
    try:
        return str(UUID(task_id))
    except ValueError:
        return None


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


def _build_channel_flags(lead) -> dict[str, bool]:
    return {
        "email": bool(getattr(lead, "work_email", None) or getattr(lead, "personal_email", None)),
        "linkedin": bool(getattr(lead, "linkedin_personal_url", None) or getattr(lead, "linkedin_url", None)),
        "whatsapp": bool(getattr(lead, "whatsapp", None)),
        "phone": bool(getattr(lead, "phone", None)),
    }


def _build_message(channel: str, lead) -> dict[str, str]:
    company = getattr(lead, "company_name", None) or "your team"
    contact_name = getattr(lead, "contact_name", None) or "there"
    title = getattr(lead, "contact_title", None) or "team"

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


def _summarize_leads(task_id: str | None) -> dict:
    selected_task_id = task_id or _latest_task_id()
    if not selected_task_id:
        return _empty_preview(None)

    leads = LEADS.get(selected_task_id, [])
    current_task = TASKS.get(selected_task_id)
    task_status = current_task.get("status") if current_task else None
    task_progress = current_task.get("progress") if current_task else None
    if not leads:
        if task_status == "running":
            return _empty_preview(
                selected_task_id,
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
                selected_task_id,
                task_status=task_status,
                task_progress=task_progress,
                next_actions=[
                    "The selected task failed before producing outreach data.",
                    "Rerun discovery or contact enrichment, then refresh this preview.",
                    "Check the task error details before trying again.",
                ],
            )
        return _empty_preview(
            selected_task_id,
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
    contacts_indexed = 0
    sample_targets = []

    for lead in leads:
        channels = _build_channel_flags(lead)
        lead_contacts = CONTACTS.get(str(getattr(lead, "id", "")), [])
        has_contact_signal = bool(
            lead_contacts
            or getattr(lead, "contact_name", None)
            or getattr(lead, "contact_title", None)
            or getattr(lead, "personal_email", None)
            or getattr(lead, "work_email", None)
            or getattr(lead, "phone", None)
            or getattr(lead, "whatsapp", None)
            or getattr(lead, "linkedin_personal_url", None)
        )
        if has_contact_signal:
            contact_count += 1
        if lead_contacts:
            contactable_lead_count += 1
        contacts_indexed += len(lead_contacts)
        for key, enabled in channels.items():
            if enabled:
                channel_counts[key] += 1
        sample_targets.append(
            {
                "lead_id": str(getattr(lead, "id", "")),
                "company_name": getattr(lead, "company_name", None),
                "contact_name": getattr(lead, "contact_name", None),
                "contact_title": getattr(lead, "contact_title", None),
                "country": getattr(lead, "country", None),
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
            bool(getattr(lead, "contact_name", None)),
            bool(getattr(lead, "company_name", None)),
        ),
    )
    active_channels = [
        name
        for name in ("email", "linkedin", "whatsapp", "phone")
        if _build_channel_flags(lead_for_messages).get(name)
    ]
    if not active_channels:
        active_channels = ["email", "linkedin"]

    message_recommendations = [_build_message(channel, lead_for_messages) for channel in active_channels[:3]]

    status = "ready" if task_status in {None, "completed", "stopped_early"} else "draft"
    return {
        "status": status,
        "task_id": selected_task_id,
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
        "next_actions": (
            [
                "The selected task is still running, so refresh once discovery finishes.",
                "Start with the highest-coverage channel and keep the first message short.",
                "Personalize the first line using the company name and contact title.",
            ]
            if task_status == "running"
            else [
                "Start with the highest-coverage channel and keep the first message short.",
                "Personalize the first line using the company name and contact title.",
                "Move high-intent replies into CRM follow-up before sending a second touch.",
            ]
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contacts_indexed": contacts_indexed,
    }


@router.get("/preview")
async def outreach_preview(task_id: str | None = Query(default=None)) -> dict:
    selected_task_id = _normalize_task_id(task_id)
    return _summarize_leads(selected_task_id)


@router.get("/stub")
async def outreach_stub() -> dict:
    return {
        "status": "planned",
        "features": [
            "Email Sequence",
            "LinkedIn InMail templates",
            "WhatsApp outreach",
            "CRM tracking",
            "Reply-rate analytics",
            "A/B testing",
        ],
    }
