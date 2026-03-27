from datetime import datetime, timezone
import uuid

from app.schemas.review import LeadReviewAnnotation
from app.services.contact.classifier import TitleClassifier
from app.services.contact.intelligence import CONTACT_SCAN_PATHS
from app.services.extraction.relevance import IndustryRelevanceClassifier
from app.services.search.keyword_cache import build_keyword_queries
from app.services.extraction.social_links import _linkedin_candidate_matches
from app.services.workspace_store import lead_to_read
from app.models.lead import Lead


def test_build_keyword_queries_use_raw_keyword_input() -> None:
    queries = build_keyword_queries(
        "laser land leveler",
        countries=["Egypt"],
        languages=["ar"],
        stage=1,
    )

    assert queries
    assert any("laser land leveler" in str(item["query"]) for item in queries)
    assert not any("ميزان ليزر للأراضي" in str(item["query"]) for item in queries)


def test_relevance_classifier_blocks_marketplaces_and_classifieds() -> None:
    classifier = IndustryRelevanceClassifier()

    ubuy = classifier.classify(
        website="https://ubuy.com.eg",
        company_name="Ubuy",
        search_title="Laser land leveler supplier",
        search_snippet="Online shopping for everything",
        homepage_html="<html><body>buy online shopping cart</body></html>",
    )
    olx = classifier.classify(
        website="https://dubizzle.com.eg",
        company_name="OLX Egypt",
        search_title="Laser equipment ads",
        search_snippet="Post ad and buy and sell",
        homepage_html="<html><body>classifieds ads buy and sell</body></html>",
    )

    assert ubuy.category in {"marketplace", "retailer"}
    assert not ubuy.is_relevant
    assert olx.category == "classifieds"
    assert not olx.is_relevant


def test_linkedin_company_candidate_validation_rejects_unrelated_company() -> None:
    unrelated = {
        "link": "https://www.linkedin.com/company/alex-power-technology/",
        "title": "Alex Power Technology | LinkedIn",
        "snippet": "Energy and power solutions",
    }
    related = {
        "link": "https://www.linkedin.com/company/surveying-systems/",
        "title": "Surveying Systems | LinkedIn",
        "snippet": "Surveying Systems engineering and measurement solutions",
    }

    assert not _linkedin_candidate_matches(unrelated, "Surveying Systems", "surveying-systems.com")
    assert _linkedin_candidate_matches(related, "Surveying Systems", "surveying-systems.com")


def test_lead_to_read_exposes_field_provenance_and_review_annotations() -> None:
    lead = Lead(
        id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        company_name="Acme",
        website="https://acme.com",
        contact_status="pending",
        decision_maker_status="pending",
        general_contact_status="pending",
        raw_data={
            "field_provenance": {
                "linkedin_url": {
                    "source_type": "website_dom",
                    "source_url": "https://acme.com/about",
                    "extractor": "website_social_dom",
                    "source_hint": "/about",
                }
            }
        },
        created_at=datetime.now(timezone.utc),
    )

    serialized = lead_to_read(
        lead,
        review_annotations={
            "linkedin_url": LeadReviewAnnotation(
                verdict="correct",
                source_path="https://acme.com/about",
                note="Found in website footer",
                updated_at=datetime.now(timezone.utc),
            )
        },
    )

    assert serialized.field_provenance is not None
    assert serialized.field_provenance["linkedin_url"]["extractor"] == "website_social_dom"
    assert serialized.review_annotations is not None
    assert serialized.review_annotations["linkedin_url"].verdict == "correct"


def test_contact_title_classifier_accepts_requested_roles_and_local_paths() -> None:
    classifier = TitleClassifier()

    assert classifier.classify("President")[0]
    assert classifier.classify("Vice President")[0]
    assert classifier.classify("Head of Technical Division")[0]
    assert classifier.classify("Director")[0]
    assert "/fale-conosco" in CONTACT_SCAN_PATHS
    assert "/kontakt" in CONTACT_SCAN_PATHS
