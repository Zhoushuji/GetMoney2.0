import asyncio
from uuid import uuid4

import pytest

from app.services.contact.intelligence import ContactIntelligenceService, LinkedInPeopleDiagnosticError


class DummyLinkedInFinder:
    def __init__(self, *, status: str, people: list[dict] | None = None, company_url: str | None = None) -> None:
        self.status = status
        self.people = people or []
        self.company_url = company_url or "https://www.linkedin.com/company/tradeinn"
        self.last_diagnostics: dict[str, object] = {}

    async def find_key_people(self, company_name: str, linkedin_company_url: str | None = None, company_website: str | None = None) -> list[dict]:
        self.last_diagnostics = {
            "company_url": linkedin_company_url or self.company_url,
            "path_b": {
                "status": self.status,
                "source_url": (linkedin_company_url or self.company_url).rstrip("/") + "/people/",
            },
        }
        return list(self.people)


def _lead(company_name: str, website: str, linkedin_url: str | None = None):
    return type(
        "Lead",
        (),
        {
            "id": uuid4(),
            "company_name": company_name,
            "website": website,
            "linkedin_url": linkedin_url,
        },
    )()


def test_find_decision_makers_surfaces_login_wall() -> None:
    service = ContactIntelligenceService()
    service.linkedin_people_finder = DummyLinkedInFinder(
        status="login_wall",
        company_url="https://www.linkedin.com/company/global-geosystems",
    )

    async def fake_fetch_site_pages(website: str | None):
        return []

    service._fetch_site_pages = fake_fetch_site_pages  # type: ignore[method-assign]

    with pytest.raises(LinkedInPeopleDiagnosticError) as exc_info:
        asyncio.run(
            service.find_decision_makers(
                _lead(
                    "Global Geosystems",
                    "https://global-geosystems.com",
                    "https://www.linkedin.com/company/global-geosystems",
                )
            )
        )

    assert exc_info.value.status == "login_wall"
    assert exc_info.value.details["linkedin_company_url"] == "https://www.linkedin.com/company/global-geosystems"


def test_find_decision_makers_treats_no_cards_as_no_data() -> None:
    service = ContactIntelligenceService()
    service.linkedin_people_finder = DummyLinkedInFinder(status="no_cards")

    async def fake_fetch_site_pages(website: str | None):
        return []

    service._fetch_site_pages = fake_fetch_site_pages  # type: ignore[method-assign]

    contacts = asyncio.run(service.find_decision_makers(_lead("Tradeinn", "https://tradeinn.com")))

    assert contacts == []


def test_path_b_candidate_without_profile_url_is_kept_from_people_page() -> None:
    service = ContactIntelligenceService()
    people = [
        {
            "person_name": "David Martin",
            "title": "CEO at Tradeinn",
            "linkedin_personal_url": None,
            "source": "path_b",
            "source_url": "https://www.linkedin.com/company/tradeinn/people/",
            "source_rank": 0,
            "priority": 1,
        }
    ]
    potentials = {"emails": [], "generic_emails": [], "phones": [], "whatsapp": [], "all": []}
    lead = _lead("Tradeinn", "https://tradeinn.com")

    verified = service._verify_people(people, lead.company_name, lead.website)
    contact = service._build_contact(lead, verified, potentials, source_urls=[lead.website])

    assert contact is not None
    assert contact.linkedin_personal_url is None
    assert "https://www.linkedin.com/company/tradeinn/people/" in (contact.source_urls or [])
