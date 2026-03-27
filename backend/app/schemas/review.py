from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

REVIEWABLE_FIELD_KEYS = (
    "company_fit",
    "company_name",
    "website",
    "facebook_url",
    "linkedin_url",
    "country",
    "contact_name",
    "contact_title",
    "linkedin_personal_url",
    "personal_email",
    "work_email",
    "phone",
    "whatsapp",
    "potential_contacts",
)


class LeadReviewAnnotation(BaseModel):
    verdict: Literal["correct", "incorrect"]
    source_path: str
    note: str | None = None
    updated_at: datetime | None = None


class LeadReviewUpsertRequest(BaseModel):
    verdict: Literal["correct", "incorrect"]
    source_path: str = Field(min_length=1)
    note: str | None = None


class LeadReviewRecord(BaseModel):
    lead_id: UUID
    field_key: str
    company_name: str | None = None
    current_value: str | None = None
    verdict: Literal["correct", "incorrect"]
    source_path: str
    note: str | None = None
    reviewed_at: datetime | None = None


class LeadReviewListResponse(BaseModel):
    items: list[LeadReviewRecord] = Field(default_factory=list)
    total: int = 0
