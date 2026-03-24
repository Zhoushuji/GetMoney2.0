from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LeadSearchRequest(BaseModel):
    product_name: str = Field(min_length=1)
    continents: list[str] = []
    countries: list[str] = []
    languages: list[str] = []
    target_count: int | None = Field(default=None, ge=1)


class LeadRead(BaseModel):
    id: UUID
    task_id: UUID
    company_name: str | None = None
    website: str | None = None
    facebook_url: str | None = None
    linkedin_url: str | None = None
    country: str | None = None
    continent: str | None = None
    source: str | None = None
    contact_status: str
    contact_name: str | None = None
    contact_title: str | None = None
    linkedin_personal_url: str | None = None
    personal_email: str | None = None
    work_email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    potential_contacts: dict[str, list[str]] | None = None
    raw_data: dict | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    items: list[LeadRead]
    total: int
    page: int
    page_size: int
