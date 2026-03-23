import re
from dataclasses import dataclass
from datetime import datetime, timezone

EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?:\+|00)?(\d{1,3})[\s\-.]?(\(?\d{1,4}\)?)[\s\-.]?(\d{1,4})[\s\-.]?(\d{1,9})")
EXCLUDED_EMAIL_PREFIXES = ["info@", "contact@", "sales@", "support@", "admin@", "hello@", "office@", "mail@", "general@", "enquiry@", "noreply@"]


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
