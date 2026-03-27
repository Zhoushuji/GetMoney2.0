import uuid
from datetime import datetime, timezone

from app.api.v1.leads import _merge_keyword_results
from app.models.company import Company
from app.models.lead import Lead
from app.models.search_keyword import SearchKeyword
from app.models.search_keyword_company import SearchKeywordCompany
from app.schemas.lead import LeadRead, LeadSearchRequest
from app.schemas.task import TaskChildSummaryResponse, TaskSummaryResponse
from app.services.search.keyword_cache import normalize_keywords, scope_fingerprint


def test_lead_search_request_normalizes_multi_keywords() -> None:
    payload = LeadSearchRequest(
        keywords=["laser land leveler", "laser land leveler", "soil compactor, land leveller"],
        countries=["Egypt"],
        languages=["en"],
        mode="live",
    )

    assert payload.keywords == ["laser land leveler", "soil compactor", "land leveller"]
    assert payload.product_name == "laser land leveler"


def test_normalize_keywords_supports_lines_and_commas() -> None:
    assert normalize_keywords(["laser\nlaser", "soil compactor，land leveller", " soil compactor "]) == [
        "laser",
        "soil compactor",
        "land leveller",
    ]


def test_scope_fingerprint_changes_with_market_scope_only() -> None:
    egypt_en = scope_fingerprint(countries=["Egypt"], languages=["en"])
    egypt_ar = scope_fingerprint(countries=["Egypt"], languages=["ar"])
    germany_en = scope_fingerprint(countries=["Germany"], languages=["en"])

    assert egypt_en != egypt_ar
    assert egypt_en != germany_en


def test_merge_keyword_results_collapses_same_company_and_unions_keywords() -> None:
    merged = _merge_keyword_results(
        [
            {
                "keyword": "laser land leveler",
                "items": [
                    {
                        "company_name": "Acme",
                        "website": "https://www.acme.com",
                        "matched_keywords": ["laser land leveler"],
                        "raw_data": {"search_title": "Acme"},
                    }
                ],
            },
            {
                "keyword": "soil compactor",
                "items": [
                    {
                        "company_name": "Acme",
                        "website": "https://acme.com/contact",
                        "matched_keywords": ["soil compactor"],
                        "raw_data": {"search_title": "Acme Contact"},
                    }
                ],
            },
        ]
    )

    assert len(merged) == 1
    assert merged[0]["matched_keywords"] == ["laser land leveler", "soil compactor"]
    assert merged[0]["raw_data"]["matched_keywords"] == ["laser land leveler", "soil compactor"]


def test_task_summary_response_exposes_keyword_counts_and_child_tasks() -> None:
    now = datetime.now(timezone.utc)
    child = TaskChildSummaryResponse(
        id=uuid.uuid4(),
        type="lead_search_keyword",
        status="completed",
        progress=100,
        confirmed_leads=5,
        mode="live",
        keyword="laser land leveler",
        cache_hit=True,
        updated_at=now,
    )
    summary = TaskSummaryResponse(
        id=uuid.uuid4(),
        type="lead_search",
        parent_task_id=None,
        status="completed",
        progress=100,
        total=10,
        completed=10,
        confirmed_leads=8,
        target_count=5,
        stopped_early=False,
        estimated_total_seconds=120,
        estimated_remaining_seconds=0,
        phase="completed",
        processed_search_requests=6,
        planned_search_requests=6,
        processed_candidates=10,
        planned_candidate_budget=10,
        results_url="/api/v1/leads?task_id=x",
        created_at=now,
        updated_at=now,
        params={"keywords": ["laser land leveler", "soil compactor"]},
        keywords=["laser land leveler", "soil compactor"],
        keyword_count=2,
        completed_keyword_count=1,
        cache_hit_keyword_count=1,
        keyword_tasks=[child],
        lead_count=8,
        decision_maker_done_count=0,
        general_contact_done_count=0,
        latest_contact_task=None,
    )

    assert summary.keyword_count == 2
    assert summary.completed_keyword_count == 1
    assert summary.cache_hit_keyword_count == 1
    assert summary.keyword_tasks[0].keyword == "laser land leveler"


def test_lead_read_supports_matched_keywords() -> None:
    now = datetime.now(timezone.utc)
    lead = Lead(
        id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        company_name="Acme",
        website="https://acme.com",
        contact_status="pending",
        decision_maker_status="pending",
        general_contact_status="pending",
        matched_keywords=["laser land leveler", "soil compactor"],
        created_at=now,
    )

    serialized = LeadRead.model_validate(lead)

    assert serialized.matched_keywords == ["laser land leveler", "soil compactor"]


def test_cache_models_expose_expected_unique_constraints() -> None:
    search_keyword_constraints = {constraint.name for constraint in SearchKeyword.__table__.constraints}
    company_constraints = {constraint.name for constraint in Company.__table__.constraints}
    link_constraints = {constraint.name for constraint in SearchKeywordCompany.__table__.constraints}

    assert "uq_search_keywords_normalized_scope" in search_keyword_constraints
    assert "uq_companies_canonical_domain" in company_constraints
    assert "uq_search_keyword_companies_keyword_company" in link_constraints
