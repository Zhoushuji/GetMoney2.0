import asyncio
import uuid
from collections import Counter

import pytest
from bs4 import BeautifulSoup

from app.api.v1 import leads as leads_module
from app.api.v1.leads import (
    SearchRuntime,
    _build_lead_item,
    _build_queries,
    _country_coverage_satisfied,
    _estimate_search_runtime,
    _keyword_fill_target,
    _minimum_country_results,
    _task_completed_units,
    _task_total_units,
)
from app.services.contact.intelligence import ContactIntelligenceService, LinkedInPeopleDiagnosticError
from app.schemas.lead import LeadSearchRequest
from app.services.extraction.country_detection import CountryDetectionResult, CountryDetector, country_gl
from app.services.search.company_extractor import CompanyNameExtractor
from app.services.search.social_links import extract_facebook, extract_linkedin_company


def test_company_name_extractor_prefers_meta_and_cleans_title():
    soup = BeautifulSoup(
        '<html><head><meta property="og:site_name" content="Best Apogee Agrotech - 20 Lakh INR"></head></html>',
        'html.parser',
    )
    item = {"title": "Buy Cheap Valves | Example"}
    extracted = asyncio.run(CompanyNameExtractor().extract(item, 'https://www.apogeeagrotech.com', soup))
    assert extracted.value == 'Apogee Agrotech'
    assert extracted.source == 'og:site_name'


def test_social_link_filters_keep_company_pages_only():
    assert extract_facebook('https://www.facebook.com/sharer.php?u=x https://www.facebook.com/apogee.agro') == 'https://www.facebook.com/apogee.agro'
    assert extract_linkedin_company('https://www.linkedin.com/in/person https://www.linkedin.com/company/apogee-agro/') == 'https://www.linkedin.com/company/apogee-agro'
    assert extract_linkedin_company('https://www.linkedin.com/in/ks-agrotech-private-limited-914903195/') == 'https://www.linkedin.com/in/ks-agrotech-private-limited-914903195'


def test_company_name_extractor_ignores_placeholder_and_prefers_domain_brand_for_generic_titles():
    soup = BeautifulSoup('<html><head><title>Future home of something quite cool.</title></head></html>', 'html.parser')
    item = {"title": "Laser Land Leveller Manufacturers - TradeIndia"}
    extracted = asyncio.run(CompanyNameExtractor().extract(item, 'https://www.tradeindia.com', soup))
    assert extracted.value == 'Tradeindia'


def test_contact_service_rejects_generic_personal_email_and_keeps_potential_contacts():
    service = ContactIntelligenceService()
    soup = BeautifulSoup(
        '''
        <html><body>
        <a href="https://www.linkedin.com/in/jane-doe">Jane Doe</a>
        <div>Jane Doe Chief Executive Officer Apogee Agrotech</div>
        <div>WhatsApp +91 98765 43210</div>
        <div>info@apogeeagrotech.com jane.doe@apogeeagrotech.com</div>
        </body></html>
        ''',
        'html.parser',
    )
    lead = type('Lead', (), {'id': __import__('uuid').uuid4(), 'website': 'https://apogeeagrotech.com', 'company_name': 'Apogee Agrotech'})
    people = service._verify_people(service._extract_linkedin_people(soup, lead.company_name), lead.company_name)
    potentials = service._extract_potential_contacts(lead.website, soup)
    contact = service._build_contact(lead, people, potentials)
    assert contact is not None
    assert contact.personal_email == 'jane.doe@apogeeagrotech.com'
    assert contact.whatsapp == '+919876543210'


def test_contact_service_safe_whatsapp_access_with_empty_list():
    service = ContactIntelligenceService()
    soup = BeautifulSoup(
        '''
        <html><body>
        <a href="https://www.linkedin.com/in/jane-doe">Jane Doe</a>
        <div>Jane Doe Chief Executive Officer Apogee Agrotech</div>
        <div>jane.doe@apogeeagrotech.com</div>
        </body></html>
        ''',
        'html.parser',
    )
    lead = type('Lead', (), {'id': __import__('uuid').uuid4(), 'website': 'https://apogeeagrotech.com', 'company_name': 'Apogee Agrotech'})
    people = service._verify_people(service._extract_linkedin_people(soup, lead.company_name), lead.company_name)
    potentials = service._extract_potential_contacts(lead.website, soup)
    contact = service._build_contact(lead, people, potentials)
    assert contact is not None
    assert contact.whatsapp is None


def test_potential_contacts_excludes_sales_email_from_general_contacts():
    service = ContactIntelligenceService()
    soup = BeautifulSoup(
        "<html><body>sales@apogeeagrotech.com info@apogeeagrotech.com</body></html>",
        "html.parser",
    )
    extracted = service._extract_potential_contacts("https://apogeeagrotech.com", soup)
    assert "sales@apogeeagrotech.com" not in extracted.get("generic_emails", [])
    assert "email:sales@apogeeagrotech.com" not in extracted.get("all", [])


class StubLinkedInPeopleFinder:
    def __init__(self, people: list[dict], diagnostics: dict):
        self.people = people
        self.last_diagnostics = {"path_b": diagnostics, "company_url": diagnostics.get("source_url")}

    async def find_key_people(self, company_name: str, linkedin_company_url: str | None = None, company_website: str | None = None) -> list[dict]:
        return list(self.people)


def _make_lead(**overrides):
    payload = {
        "id": uuid.uuid4(),
        "website": "https://tradeinn.com",
        "company_name": "Tradeinn",
        "linkedin_url": "https://www.linkedin.com/company/tradeinn",
    }
    payload.update(overrides)
    return type("Lead", (), payload)


def test_contact_service_keeps_path_b_people_without_profile_url():
    service = ContactIntelligenceService()
    service.linkedin_people_finder = StubLinkedInPeopleFinder(
        [
            {
                "person_name": "Jane Doe",
                "title": "CEO at Tradeinn",
                "linkedin_personal_url": None,
                "source": "path_b",
                "source_url": "https://www.linkedin.com/company/tradeinn/people/",
                "source_rank": 0,
            }
        ],
        {"status": "parsed", "source_url": "https://www.linkedin.com/company/tradeinn/people/"},
    )
    service._fetch_site_pages = lambda website: asyncio.sleep(0, result=[])
    contacts = asyncio.run(service.find_decision_makers(_make_lead()))
    assert len(contacts) == 1
    assert contacts[0].person_name == "Jane Doe"
    assert contacts[0].title == "CEO"
    assert "https://www.linkedin.com/company/tradeinn/people/" in (contacts[0].source_urls or [])


def test_contact_service_raises_on_linkedin_selector_miss():
    service = ContactIntelligenceService()
    service.linkedin_people_finder = StubLinkedInPeopleFinder(
        [],
        {"status": "selector_miss", "source_url": "https://www.linkedin.com/company/global-geosystems/people/"},
    )
    service._fetch_site_pages = lambda website: asyncio.sleep(0, result=[])
    with pytest.raises(LinkedInPeopleDiagnosticError) as exc_info:
        asyncio.run(service.find_decision_makers(_make_lead(company_name="Global Geosystems", website="https://global-geosystems.com", linkedin_url="https://www.linkedin.com/company/global-geosystems")))
    assert getattr(exc_info.value, "status", None) == "selector_miss"
    assert exc_info.value.details["linkedin_path_diagnostics"]["status"] == "selector_miss"


def test_contact_service_treats_no_cards_as_no_data():
    service = ContactIntelligenceService()
    service.linkedin_people_finder = StubLinkedInPeopleFinder(
        [],
        {"status": "no_cards", "source_url": "https://www.linkedin.com/company/global-geosystems/people/"},
    )
    service._fetch_site_pages = lambda website: asyncio.sleep(0, result=[])
    contacts = asyncio.run(
        service.find_decision_makers(
            _make_lead(
                company_name="Global Geosystems",
                website="https://global-geosystems.com",
                linkedin_url="https://www.linkedin.com/company/global-geosystems",
            )
        )
    )
    assert contacts == []


def test_contact_service_skips_linkedin_diagnostics_for_demo_leads():
    service = ContactIntelligenceService()
    service.linkedin_people_finder = StubLinkedInPeopleFinder(
        [],
        {"status": "captcha_or_block", "source_url": "https://www.linkedin.com/company/demo-company/people/"},
    )
    contacts = asyncio.run(
        service.find_decision_makers(
            _make_lead(
                website="https://example.com/demo/laser/germany/1",
                company_name="Demo Company",
                linkedin_url="https://www.linkedin.com/company/demo-company",
                source="demo",
                raw_data={"demo_mode": True},
            )
        )
    )
    potentials = asyncio.run(
        service.find_potential_contacts(
            _make_lead(
                website="https://example.com/demo/laser/germany/1",
                company_name="Demo Company",
                linkedin_url="https://www.linkedin.com/company/demo-company",
                source="demo",
                raw_data={"demo_mode": True},
            )
        )
    )
    assert contacts == []
    assert potentials["emails"] == []
    assert potentials["source_urls"] == ["https://example.com/demo/laser/germany/1"]


def test_estimate_search_runtime_tracks_target_budget():
    payload = LeadSearchRequest(
        product_name="laser",
        countries=["Germany", "Austria"],
        languages=["en", "de"],
        target_count=20,
        mode="live",
    )
    estimated = _estimate_search_runtime(payload)
    assert estimated["planned_search_requests"] == 80
    assert estimated["planned_candidate_budget"] == 40
    assert estimated["estimated_total_seconds"] > 200


def test_estimate_search_runtime_demo_is_small():
    payload = LeadSearchRequest(
        product_name="laser",
        countries=["Germany"],
        languages=["en"],
        target_count=5,
        mode="demo",
    )
    estimated = _estimate_search_runtime(payload)
    assert estimated["planned_search_requests"] == 0
    assert estimated["planned_candidate_budget"] == 5
    assert estimated["estimated_total_seconds"] == 2


def test_build_queries_use_target_country_gl_and_local_language_term():
    payload = LeadSearchRequest(
        product_name="laser land leveler",
        countries=["Egypt"],
        languages=["en", "ar"],
        target_count=20,
        mode="live",
    )
    queries = _build_queries(payload)
    assert {query["gl"] for query in queries} == {"eg"}
    assert country_gl("Germany") == "de"
    assert country_gl("Brazil") == "br"
    assert any(query["language"] == "en" and "Egypt" in query["query"] for query in queries)
    assert any(query["language"] == "ar" and "مصر" in query["query"] for query in queries)


def test_build_queries_expand_land_level_variants_and_templates():
    payload = LeadSearchRequest(
        product_name="laser land level",
        countries=["Pakistan"],
        languages=["en", "ur"],
        mode="live",
    )
    queries = _build_queries(payload, keyword="laser land level", stage=1)

    query_texts = {str(item["query"]) for item in queries}
    assert any("laser land leveler" in query for query in query_texts)
    assert any("laser land leveller" in query for query in query_texts)
    assert any("gps land leveler" in query for query in query_texts)
    assert any(" dealer in " in query for query in query_texts)
    assert any(" distributor in " in query for query in query_texts)


def test_build_queries_do_not_cross_join_unrelated_country_languages():
    payload = LeadSearchRequest(
        product_name="laser land leveler",
        countries=["Thailand", "Vietnam", "Pakistan"],
        languages=["en", "th", "vi", "ur"],
        mode="live",
    )

    queries = _build_queries(payload)

    thailand_languages = {query["language"] for query in queries if query["country"] == "Thailand"}
    vietnam_languages = {query["language"] for query in queries if query["country"] == "Vietnam"}
    pakistan_languages = {query["language"] for query in queries if query["country"] == "Pakistan"}

    assert thailand_languages == {"en", "th"}
    assert vietnam_languages == {"en", "vi"}
    assert pakistan_languages == {"en", "ur"}
    assert len(queries) == 120


def test_build_queries_interleave_countries_early_in_primary_round():
    payload = LeadSearchRequest(
        product_name="laser land level",
        countries=["Thailand", "Vietnam", "Pakistan"],
        languages=["en", "th", "vi", "ur"],
        mode="live",
    )

    queries = _build_queries(payload, keyword="laser land level", stage=1)
    first_six_countries = [str(query["country"]) for query in queries[:6]]

    assert first_six_countries == ["Thailand", "Thailand", "Vietnam", "Vietnam", "Pakistan", "Pakistan"]


def test_estimate_search_runtime_open_ended_is_capped_for_multi_country_search():
    payload = LeadSearchRequest(
        product_name="laser land leveler",
        countries=["Thailand", "Vietnam", "Pakistan"],
        languages=["en", "th", "vi", "ur"],
        mode="live",
    )

    estimated = _estimate_search_runtime(payload)

    assert estimated["planned_search_requests"] == 150
    assert estimated["planned_candidate_budget"] == 120
    assert estimated["estimated_total_seconds"] < 1000


def test_open_ended_fill_target_scales_with_country_count():
    payload = LeadSearchRequest(
        product_name="laser land level",
        countries=["Thailand", "Vietnam", "Pakistan"],
        languages=["en", "th", "vi", "ur"],
        mode="live",
    )

    assert _keyword_fill_target(payload) == 30


def test_multi_country_open_ended_search_requires_at_least_one_result_per_country():
    payload = LeadSearchRequest(
        product_name="laser land level",
        countries=["Thailand", "Vietnam", "Pakistan"],
        languages=["en", "th", "vi", "ur"],
        mode="live",
    )

    assert _minimum_country_results(payload) == 1
    assert _country_coverage_satisfied(payload, Counter({"Thailand": 10, "Vietnam": 8})) is False
    assert _country_coverage_satisfied(payload, Counter({"Thailand": 10, "Vietnam": 8, "Pakistan": 1})) is True


def test_task_completed_units_cap_candidate_progress_to_budget():
    task = type(
        "TaskStub",
        (),
        {
            "processed_search_requests": 101,
            "processed_candidates": 932,
            "planned_search_requests": 440,
            "planned_candidate_budget": 240,
        },
    )()

    assert _task_total_units(task) == 680
    assert _task_completed_units(task) == 341


def test_country_detector_rejects_india_for_egypt_target():
    detector = CountryDetector()
    result = asyncio.run(
        detector.detect(
            website="https://laserco.in",
            target_country="Egypt",
            search_title="Laser land leveler supplier in Egypt",
            search_snippet="Manufacturer exporting to Egypt and Africa",
            homepage_html="""
            <html><body>
            <div>Contact us</div>
            <div>Ahmedabad, India</div>
            <div>Phone: +91 98765 43210</div>
            </body></html>
            """,
        )
    )
    assert result.detected_country_code == "IN"
    assert result.status == "mismatch"
    assert result.mismatch_reason is not None


def test_country_detector_keeps_com_site_with_egypt_structured_data_and_phone():
    detector = CountryDetector()
    result = asyncio.run(
        detector.detect(
            website="https://precision-laser.com",
            target_country="Egypt",
            search_title="Laser land leveler supplier",
            search_snippet="Trusted leveling systems",
            homepage_html="""
            <html>
              <head>
                <script type="application/ld+json">
                  {"@type":"Organization","address":{"addressCountry":"Egypt"}}
                </script>
              </head>
              <body>
                <div>Address: Cairo, Egypt</div>
                <div>Phone: +20 2 1234 5678</div>
              </body>
            </html>
            """,
        )
    )
    assert result.detected_country_code == "EG"
    assert result.status == "matched"
    assert any(item["signal"] == "homepage_structured" for item in result.evidence)


def test_build_lead_item_discards_non_target_country(monkeypatch: pytest.MonkeyPatch):
    async def fake_fetch_homepage(website: str):
        html = "<html><body>Laser India</body></html>"
        return BeautifulSoup(html, "html.parser"), html

    async def fake_company_name_extract(self, url: str, serper_result=None, homepage_html=None):
        return "Laser India"

    async def fake_country_detect(self, **kwargs):
        return CountryDetectionResult(
            target_country_code="EG",
            target_country_name="Egypt",
            detected_country_code="IN",
            detected_country_name="India",
            continent="Asia",
            confidence=0.91,
            evidence=({"country_code": "IN", "country_name": "India", "signal": "cc_tld", "value": ".in", "weight": 4},),
            mismatch_reason="Detected India instead of target market Egypt.",
        )

    async def fake_social_extract(self, company_name: str, domain: str):
        return {"facebook": None, "linkedin": None}

    monkeypatch.setattr(leads_module, "_fetch_homepage", fake_fetch_homepage)
    monkeypatch.setattr(leads_module.CompanyNameExtractor, "extract", fake_company_name_extract)
    monkeypatch.setattr(leads_module.CountryDetector, "detect", fake_country_detect)
    monkeypatch.setattr(leads_module.SocialLinksExtractor, "extract", fake_social_extract)

    lead_item = asyncio.run(
        _build_lead_item(
            SearchRuntime(),
            {"link": "https://laserco.in", "title": "Laser India", "snippet": "India manufacturer"},
            "Egypt",
        )
    )
    assert lead_item is None


def test_build_lead_item_uses_detected_country(monkeypatch: pytest.MonkeyPatch):
    async def fake_fetch_homepage(website: str):
        html = "<html><body>Laser Egypt</body></html>"
        return BeautifulSoup(html, "html.parser"), html

    async def fake_company_name_extract(self, url: str, serper_result=None, homepage_html=None):
        return "Laser Egypt"

    async def fake_country_detect(self, **kwargs):
        return CountryDetectionResult(
            target_country_code="EG",
            target_country_name="Egypt",
            detected_country_code="EG",
            detected_country_name="Egypt",
            continent="Africa",
            confidence=0.93,
            evidence=({"country_code": "EG", "country_name": "Egypt", "signal": "homepage_phone", "value": "+20 2 1234 5678", "weight": 4},),
            mismatch_reason=None,
        )

    async def fake_social_extract(self, company_name: str, domain: str):
        return {"facebook": "https://www.facebook.com/laser-eg", "linkedin": "https://www.linkedin.com/company/laser-eg"}

    monkeypatch.setattr(leads_module, "_fetch_homepage", fake_fetch_homepage)
    monkeypatch.setattr(leads_module.CompanyNameExtractor, "extract", fake_company_name_extract)
    monkeypatch.setattr(leads_module.CountryDetector, "detect", fake_country_detect)
    monkeypatch.setattr(leads_module.SocialLinksExtractor, "extract", fake_social_extract)

    lead_item = asyncio.run(
        _build_lead_item(
            SearchRuntime(),
            {"link": "https://precision-laser.com", "title": "Laser Egypt", "snippet": "Egypt supplier"},
            "Egypt",
        )
    )
    assert lead_item is not None
    assert lead_item["country"] == "Egypt"
    assert lead_item["continent"] == "Africa"
    assert lead_item["raw_data"]["country_detection"]["status"] == "matched"
