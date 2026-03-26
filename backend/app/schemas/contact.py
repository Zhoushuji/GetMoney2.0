from datetime import datetime
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, Field


class ContactEnrichRequest(BaseModel):
    lead_ids: list[UUID]
    mode: Literal["all", "decision_maker", "general_contact"] = "all"


class ContactEnrichAllRequest(BaseModel):
    task_id: UUID


class ContactRead(BaseModel):
    id: UUID
    lead_id: UUID
    person_name: str | None = None
    title: str | None = None
    priority: int | None = None
    personal_email: str | None = None
    work_email: str | None = None
    linkedin_personal_url: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    potential_contacts: dict[str, list[str]] | None = None
    source_urls: list[str] | None = None
    verified_at: datetime | None = None

    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    contacts: list[ContactRead] = Field(default_factory=list)


class ContactPotentialContactsResponse(BaseModel):
    phone: str | None = None
    whatsapp: str | None = None
    general_emails: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)


class ContactStatusResponse(BaseModel):
    lead_id: UUID
    decision_maker_status: str
    general_contact_status: str
    contacts: list[ContactRead] = Field(default_factory=list)
    potential_contacts: ContactPotentialContactsResponse | None = None
    error: str | None = None
    error_details: dict | None = None
