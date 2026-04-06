from datetime import datetime, timezone
import uuid

from app.api.v1.leads import _extract_official_website
from app.models.lead import Lead
from app.schemas.lead import LeadRead, LeadSearchRequest
from app.services.extraction.relevance import IndustryRelevanceClassifier
from app.services.search.country_sources import (
    build_source_entity_key,
    classify_result_page,
    direct_result_page_priority,
    is_direct_result_page,
    resolve_country_search_sources,
)
from app.services.search.keyword_cache import build_keyword_queries
from app.services.workspace_store import lead_to_read


def test_land_level_query_expansion_includes_trade_discovery_terms() -> None:
    queries = build_keyword_queries(
        "laser land level",
        countries=["India"],
        languages=["en"],
        stage=1,
    )

    rendered = " | ".join(str(item["query"]).lower() for item in queries)
    source_pairs = {(str(item["source_type"]), str(item["source_name"])) for item in queries}
    assert "laser land leveler" in rendered
    assert "laser land leveller" in rendered
    assert "land leveler" in rendered
    assert "land leveller" in rendered
    assert "gps land level" in rendered
    assert "gps land leveler" in rendered
    assert "rtk land leveler" in rendered
    assert "dealer" in rendered
    assert "distributor" in rendered
    assert "trader" in rendered
    assert ("directory", "justdial") in source_pairs
    assert ("marketplace", "indiamart") in source_pairs
    assert ("marketplace", "tradeindia") in source_pairs
    assert ("marketplace", "exportersindia") in source_pairs
    first_web_index = next(index for index, item in enumerate(queries) if item["source_type"] == "website")
    first_indiamart_profile_index = next(
        index
        for index, item in enumerate(queries)
        if item["source_name"] == "indiamart" and "profile.html" in str(item["query"])
    )
    first_indiamart_second_variant_index = next(
        index
        for index, item in enumerate(queries)
        if item["source_name"] == "indiamart" and str(item["query"]) == 'site:indiamart.com "laser land leveler" "profile.html"'
    )
    first_indiamart_fallback_index = next(
        index
        for index, item in enumerate(queries)
        if item["source_name"] == "indiamart" and str(item["query"]) == 'site:indiamart.com "laser land level"'
    )
    first_tradeindia_entity_index = next(
        index
        for index, item in enumerate(queries)
        if item["source_name"] == "tradeindia" and str(item["query"]) == 'site:tradeindia.com/products "laser land level"'
    )
    first_justdial_entity_index = next(
        index
        for index, item in enumerate(queries)
        if item["source_name"] == "justdial" and str(item["query"]) == 'site:justdial.com/shop-online "laser land level"'
    )
    assert first_indiamart_profile_index < first_web_index < first_indiamart_fallback_index
    assert first_tradeindia_entity_index < first_indiamart_second_variant_index
    assert first_justdial_entity_index < first_indiamart_second_variant_index


def test_india_default_directory_sources_are_resolved_before_search() -> None:
    india_sources = resolve_country_search_sources("India")
    directory_names = [item.name for item in india_sources["directory_sources"]]
    marketplace_names = [item.name for item in india_sources["marketplace_sources"]]
    social_names = [item.name for item in india_sources["social_sources"]]

    assert india_sources["country_code"] == "IN"
    assert "in_yellow_pages" in directory_names
    assert "justdial" in directory_names
    assert marketplace_names == ["indiamart", "tradeindia", "exportersindia"]
    assert social_names == ["linkedin_company", "facebook_page", "instagram_profile", "tiktok_profile"]


def test_generic_directory_homepage_must_not_be_promoted_as_final_result() -> None:
    classifier = IndustryRelevanceClassifier()
    result = classifier.classify(
        website="https://www.indiamart.com",
        company_name="IndiaMART",
        search_title="IndiaMART - Business Directory",
        search_snippet="Find suppliers, buyers, and products",
        homepage_html="<html><body>business directory supplier marketplace search results</body></html>",
    )

    assert not result.is_relevant
    assert result.category != "relevant"


def test_directory_and_social_entity_pages_are_classified_as_non_direct_results() -> None:
    assert classify_result_page(
        "https://www.indiamart.com",
        source_name="indiamart",
        source_type="marketplace",
    ) == "directory_home"
    assert not is_direct_result_page(
        "https://www.indiamart.com",
        source_name="indiamart",
        source_type="marketplace",
    )
    assert classify_result_page(
        "https://www.indiamart.com/m-s-bharat-agriculture-26877380/",
        source_name="indiamart",
        source_type="marketplace",
    ) == "store_profile"
    assert is_direct_result_page(
        "https://www.indiamart.com/m-s-bharat-agriculture-26877380/",
        source_name="indiamart",
        source_type="marketplace",
    )
    assert classify_result_page(
        "https://www.facebook.com/sharer.php?u=x",
        source_name="facebook_page",
        source_type="social",
    ) == "search_results_page"
    assert not is_direct_result_page(
        "https://www.facebook.com/sharer.php?u=x",
        source_name="facebook_page",
        source_type="social",
    )
    assert classify_result_page(
        "https://my.indiamart.com",
        source_name="indiamart",
        source_type="marketplace",
    ) == "aggregator_page"
    assert not is_direct_result_page(
        "https://pdf.indiamart.com",
        source_name="indiamart",
        source_type="marketplace",
    )
    assert classify_result_page(
        "https://www.tradeindia.com/search.html?keyword=laser+land+leveler",
        source_name="tradeindia",
        source_type="marketplace",
    ) == "search_results_page"
    assert classify_result_page(
        "https://www.tradeindia.com/m-s-bharat-agriculture-26877380/",
        source_name="tradeindia",
        source_type="marketplace",
    ) == "company_profile"
    assert classify_result_page(
        "https://www.tradeindia.com/products/laser-land-leveler.html",
        source_name="tradeindia",
        source_type="marketplace",
    ) == "store_profile"
    assert classify_result_page(
        "https://www.justdial.com/Ludhiana/Spltech/9999PX161-X161-230101000001-A1B2_BZDET",
        source_name="justdial",
        source_type="directory",
    ) == "company_profile"
    assert classify_result_page(
        "https://www.justdial.com/jdmart/Ludhiana/Laser-Land-Leveller/jdm-14552-ENT-11223344",
        source_name="justdial",
        source_type="directory",
    ) == "store_profile"
    assert classify_result_page(
        "https://www.justdial.com/shop-online/Laser-Land-Leveler/jdm-1299836-ent-6-13259455",
        source_name="justdial",
        source_type="directory",
    ) == "store_profile"
    assert classify_result_page(
        "https://www.justdial.com/Ludhiana/Laser-Land-Leveler/nct-12345678",
        source_name="justdial",
        source_type="directory",
    ) == "search_results_page"
    assert classify_result_page(
        "https://www.justdial.com/india/laser-land-leveler",
        source_name="justdial",
        source_type="directory",
    ) == "search_results_page"
    assert classify_result_page(
        "https://www.exportersindia.com/punjab/laser-land-leveler.htm",
        source_name="exportersindia",
        source_type="marketplace",
    ) == "listing_page"
    assert not is_direct_result_page(
        "https://www.exportersindia.com/muzaffarnagar/laser-land-leveler.htm",
        source_name="exportersindia",
        source_type="marketplace",
    )
    assert classify_result_page(
        "https://www.exportersindia.com/gill-works-ajner/",
        source_name="exportersindia",
        source_type="marketplace",
    ) == "company_profile"
    assert classify_result_page(
        "https://www.exportersindia.com/product-detail/yellow-or-red-laser-land-leveler-2523393295.htm",
        source_name="exportersindia",
        source_type="marketplace",
    ) == "store_profile"


def test_marketplace_entity_key_merges_profile_and_store_pages_for_same_seller() -> None:
    profile_key = build_source_entity_key(
        "https://www.indiamart.com/s3technics-noida/profile.html",
        source_name="indiamart",
        source_type="marketplace",
        company_name="S3 Technics",
        country="India",
    )
    store_key = build_source_entity_key(
        "https://www.indiamart.com/s3technics-noida/laser-land-leveler.html",
        source_name="indiamart",
        source_type="marketplace",
        company_name="Laser Land Leveler",
        country="India",
    )
    assert profile_key == "indiamart:s3technics-noida"
    assert store_key == profile_key
    assert direct_result_page_priority("company_profile") > direct_result_page_priority("store_profile")


def test_tradeindia_entity_key_merges_profile_and_product_pages_for_same_seller() -> None:
    profile_key = build_source_entity_key(
        "https://www.tradeindia.com/m-s-bharat-agriculture-26877380/",
        source_name="tradeindia",
        source_type="marketplace",
        company_name="Bharat Agriculture",
        country="India",
    )
    product_key = build_source_entity_key(
        "https://www.tradeindia.com/products/agricultural-laser-land-leveler-3347476.html",
        source_name="tradeindia",
        source_type="marketplace",
        company_name="Bharat Agriculture",
        country="India",
    )
    assert profile_key == "tradeindia:india:bharat-agriculture"
    assert product_key == profile_key


def test_tradeindia_entity_key_prefers_url_token_over_unknown_company_name() -> None:
    entity_key = build_source_entity_key(
        "https://www.tradeindia.com/m-s-bharat-agriculture-26877380/",
        source_name="tradeindia",
        source_type="marketplace",
        company_name="Unknown company",
        country="India",
    )

    assert entity_key == "tradeindia:india:bharat-agriculture"


def test_justdial_entity_key_merges_store_and_detail_pages_for_same_seller() -> None:
    detail_key = build_source_entity_key(
        "https://www.justdial.com/Ludhiana/Celec/9999PX161-X161-230101000001-A1B2_BZDET",
        source_name="justdial",
        source_type="directory",
        company_name="Celec",
        country="India",
    )
    store_key = build_source_entity_key(
        "https://www.justdial.com/jdmart/Ludhiana/Laser-Land-Leveler/pid-2024410947/0161PX161-X161-100917164747-D2M4",
        source_name="justdial",
        source_type="directory",
        company_name="Celec",
        country="India",
    )
    assert detail_key == "justdial:india:celec"
    assert store_key == detail_key


def test_justdial_entity_key_prefers_url_token_over_unknown_company_name() -> None:
    entity_key = build_source_entity_key(
        "https://www.justdial.com/Ludhiana/Celec/9999PX161-X161-230101000001-A1B2_BZDET",
        source_name="justdial",
        source_type="directory",
        company_name="Unknown company",
        country="India",
    )

    assert entity_key == "justdial:india:celec"


def test_no_website_listing_payload_can_carry_source_metadata() -> None:
    lead = Lead(
        id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        company_name="Bharat Agriculture",
        website=None,
        facebook_url=None,
        linkedin_url=None,
        country="India",
        continent="Asia",
        source="marketplace",
        contact_status="pending",
        decision_maker_status="pending",
        general_contact_status="pending",
        matched_keywords=["laser land level"],
        source_url="https://www.tradeindia.com/m-s-bharat-agriculture-26877380/",
        source_type="marketplace",
        raw_data={
            "source_url": "https://www.tradeindia.com/m-s-bharat-agriculture-26877380/",
            "source_type": "marketplace",
            "entity_page_type": "company_profile",
        },
        created_at=datetime.now(timezone.utc),
    )

    serialized = lead_to_read(lead)

    assert isinstance(serialized, LeadRead)
    assert serialized.website is None
    assert serialized.source_url == "https://www.tradeindia.com/m-s-bharat-agriculture-26877380/"
    assert serialized.source_type == "marketplace"
    assert serialized.raw_data is not None
    assert serialized.raw_data["source_url"] == "https://www.tradeindia.com/m-s-bharat-agriculture-26877380/"
    assert serialized.raw_data["source_type"] == "marketplace"
    assert serialized.raw_data["entity_page_type"] == "company_profile"


def test_marketplace_official_website_extraction_requires_explicit_site_link() -> None:
    html = """
    <html><body>
      <a href="https://twitter.com/example-company">Twitter</a>
      <a href="https://my.indiamart.com/">IndiaMART Pro</a>
      <a href="https://example.com">Visit Website</a>
    </body></html>
    """
    assert _extract_official_website(
        "https://www.indiamart.com/example-company/profile.html",
        html,
        source_type="marketplace",
    ) == "https://example.com"
