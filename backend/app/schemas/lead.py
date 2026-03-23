from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LeadSearchRequest(BaseModel):
    product_name: str = Field(min_length=1)
    continents: list[str] = []
    countries: list[str] = []
    languages: list[str] = []
    channels: list[str] = ["google", "bing", "facebook", "linkedin", "yellowpages"]


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
    raw_data: dict | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    items: list[LeadRead]
    total: int
    page: int
    page_size: int
