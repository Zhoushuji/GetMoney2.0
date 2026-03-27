from datetime import datetime
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.review import LeadReviewAnnotation
from app.services.search.keyword_cache import normalize_keywords


class LeadSearchRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    product_name: str | None = Field(default=None, min_length=1)
    continents: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    target_count: int | None = Field(default=None, ge=1)
    mode: Literal["live", "demo"] = "live"

    @model_validator(mode="after")
    def validate_keywords(self) -> "LeadSearchRequest":
        source_keywords = list(self.keywords)
        if self.product_name:
            source_keywords.append(self.product_name)
        normalized = normalize_keywords(source_keywords)
        if not normalized:
            raise ValueError("at least one keyword is required")
        self.keywords = normalized
        if not self.product_name:
            self.product_name = normalized[0]
        return self


class LeadRead(BaseModel):
    id: UUID
    task_id: UUID
    company_name: str | None = None
    website: str | None = None
    facebook_url: str | None = None
    linkedin_url: str | None = None
    country: str | None = None
    continent: str | None = None
    matched_keywords: list[str] | None = None
    source: str | None = None
    contact_status: str
    decision_maker_status: str = "pending"
    general_contact_status: str = "pending"
    contact_name: str | None = None
    contact_title: str | None = None
    linkedin_personal_url: str | None = None
    personal_email: str | None = None
    work_email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    potential_contacts: dict[str, list[str]] | None = None
    general_emails: list[str] | None = None
    field_provenance: dict | None = None
    review_annotations: dict[str, LeadReviewAnnotation] | None = None
    raw_data: dict | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    items: list[LeadRead]
    total: int
    page: int
    page_size: int
