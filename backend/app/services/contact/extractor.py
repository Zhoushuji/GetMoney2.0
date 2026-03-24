import re
from dataclasses import dataclass
from datetime import datetime, timezone

EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?:\+|00)?(\d{1,3})[\s\-.]?(\(?\d{1,4}\)?)[\s\-.]?(\d{1,4})[\s\-.]?(\d{1,9})")
EXCLUDED_EMAIL_PREFIXES = ["info@", "contact@", "sales@", "support@", "admin@", "hello@", "office@", "mail@", "general@", "enquiry@", "noreply@"]
INVALID_PERSON_NAME_PATTERNS = [
    re.compile(r"^[A-Z][a-z]+ Contact$"),
    re.compile(r"^[A-Z][a-z]+ (Info|Team|Admin|Support|Sales)$"),
    re.compile(r"^\w{1,3}$"),
]


@dataclass
class ContactInfo:
    person_name: str
    title: str
    priority: int
    personal_email: str | None
    work_email: str | None
    linkedin_url: str | None
    phone: str | None
    whatsapp: str | None
    source_urls: list[str]
    confidence: float
    verified_at: datetime = datetime.now(timezone.utc)


def _is_invalid_person_name(name: str) -> bool:
    return any(pattern.search(name) for pattern in INVALID_PERSON_NAME_PATTERNS)


def _build_contact(raw: dict) -> ContactInfo | None:
    def safe_first(lst: list, default=None):
        return lst[0] if lst else default

    person_name = (raw.get("person_name") or "").strip()
    if not person_name or _is_invalid_person_name(person_name):
        return None

    return ContactInfo(
        person_name=person_name,
        title=raw.get("title", ""),
        priority=raw.get("priority", 4),
        personal_email=safe_first(raw.get("personal_emails", [])),
        work_email=safe_first(raw.get("work_emails", [])),
        linkedin_url=safe_first(raw.get("linkedin_urls", [])),
        phone=safe_first(raw.get("phones", [])),
        whatsapp=safe_first(raw.get("whatsapp", [])),
        source_urls=raw.get("source_urls", []),
        confidence=float(raw.get("confidence", 0.5)),
        verified_at=datetime.now(timezone.utc),
    )


def is_personal_email(email: str, person_name: str | None = None, company_domain: str | None = None) -> float:
    lower_email = email.lower()
    if any(lower_email.startswith(prefix) for prefix in EXCLUDED_EMAIL_PREFIXES):
        return 0.0
    score = 0.2
    if person_name:
        tokens = [token.lower() for token in person_name.split() if token]
        if any(token in lower_email for token in tokens):
            score += 0.6
    if company_domain and lower_email.endswith(f"@{company_domain}"):
        score += 0.2
    return min(score, 1.0)
