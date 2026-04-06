import asyncio

from bs4 import BeautifulSoup
import pytest

from app.api.v1 import leads as leads_module
from app.api.v1.leads import SearchRuntime, _build_lead_item
from app.services.extraction.country_detection import CountryDetectionResult
from app.services.search.social_resolution import (
    build_company_social_queries,
    choose_best_social_resolution,
    classify_social_url,
    recover_social_profile_url,
    resolve_social_result,
)


def test_social_url_classification_and_profile_recovery_cover_all_platforms() -> None:
    fb_post = classify_social_url("https://www.facebook.com/apogeeprecision/posts/123")
    assert fb_post.page_type == "social_post_page"
    assert recover_social_profile_url("https://www.facebook.com/apogeeprecision/posts/123", fb_post) == "https://www.facebook.com/apogeeprecision"

    li_company_sub = classify_social_url("https://www.linkedin.com/company/apogee-precision/posts/")
    assert li_company_sub.page_type == "social_subpage"
    assert recover_social_profile_url("https://www.linkedin.com/company/apogee-precision/posts/", li_company_sub) == "https://www.linkedin.com/company/apogee-precision"

    tt_video = classify_social_url("https://www.tiktok.com/@apogeeprecision/video/123")
    assert tt_video.page_type == "video_page"
    assert recover_social_profile_url("https://www.tiktok.com/@apogeeprecision/video/123", tt_video) == "https://www.tiktok.com/@apogeeprecision"

    ig_reel = classify_social_url("https://www.instagram.com/apogeeprecision/reel/ABC123/")
    assert ig_reel.page_type == "video_page"
    assert recover_social_profile_url("https://www.instagram.com/apogeeprecision/reel/ABC123/", ig_reel) == "https://www.instagram.com/apogeeprecision/"


def test_social_resolution_prefers_recovered_official_profile() -> None:
    resolution = resolve_social_result(
        company_name="Apogee Precision Laser",
        result={
            "link": "https://www.facebook.com/apogeeprecisionlaser/posts/101",
            "title": "Apogee Precision Laser",
            "snippet": "Official updates from Apogee Precision Laser",
        },
    )

    assert resolution.decision == "accepted_recovered_profile"
    assert resolution.official_profile_url == "https://www.facebook.com/apogeeprecisionlaser"
    assert resolution.selected_url == "https://www.facebook.com/apogeeprecisionlaser"


def test_social_resolution_rejects_platform_account_even_when_title_mentions_company() -> None:
    resolution = resolve_social_result(
        company_name="Apogee Precision Lasers",
        result={
            "link": "https://www.facebook.com/tradeindia",
            "title": "Apogee Precision Lasers - TradeIndia",
            "snippet": "TradeIndia listing for Apogee Precision Lasers in India",
        },
    )

    assert resolution.decision == "rejected_low_score"
    assert resolution.selected_url is None
    assert resolution.official_profile_url == "https://www.facebook.com/tradeindia"


def test_social_resolution_rejects_invalid_instagram_help_pages() -> None:
    resolution = resolve_social_result(
        company_name="Apogee Precision Lasers",
        result={
            "link": "https://help.instagram.com/896353301143942/",
            "title": "Instagram Help Center",
            "snippet": "Learn how to use Instagram",
        },
    )

    assert resolution.decision == "rejected_structural"
    assert resolution.selected_url is None


def test_social_resolution_allows_high_score_linkedin_personal_page_as_source_only() -> None:
    resolution = resolve_social_result(
        company_name="Apogee Precision Laser",
        result={
            "link": "https://www.linkedin.com/in/apogeeprecisionlaser",
            "title": "Apogee Precision Laser | LinkedIn",
            "snippet": "Apogee Precision Laser founder and operations lead",
        },
    )

    assert resolution.decision == "accepted_direct_high_score"
    assert resolution.selected_url == "https://www.linkedin.com/in/apogeeprecisionlaser"
    assert resolution.official_profile_url is None


def test_choose_best_social_resolution_prefers_direct_profile_over_post() -> None:
    results = [
        {
            "link": "https://www.instagram.com/apogeeprecision/",
            "title": "Apogee Precision",
            "snippet": "Official Instagram for Apogee Precision",
        },
        {
            "link": "https://www.instagram.com/apogeeprecision/p/123/",
            "title": "Apogee Precision",
            "snippet": "Post from Apogee Precision",
        },
    ]

    best = choose_best_social_resolution(
        "Apogee Precision",
        platform="instagram",
        results=results,
    )

    assert best is not None
    assert best.decision == "accepted_direct_profile"
    assert best.selected_url == "https://www.instagram.com/apogeeprecision/"


def test_company_social_query_builder_expands_all_platforms() -> None:
    queries = build_company_social_queries("Apogee Precision", product="laser land leveler", country="India")

    assert queries["facebook"][0] == 'site:facebook.com "Apogee Precision"'
    assert any("laser land leveler" in query for query in queries["instagram"])
    assert any("India" in query for query in queries["linkedin"])


def test_build_lead_item_accepts_social_post_and_uses_recovered_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <html>
      <head><title>Apogee Precision Laser</title></head>
      <body><h1>Apogee Precision Laser</h1></body>
    </html>
    """

    async def fake_fetch_homepage(website: str):
        return BeautifulSoup(html, "html.parser"), html

    async def fake_company_name_extract(self, url: str, serper_result=None, homepage_html=None):
        return "Apogee Precision Laser"

    async def fake_country_detect(self, **kwargs):
        return CountryDetectionResult(
            target_country_code="IN",
            target_country_name="India",
            detected_country_code="IN",
            detected_country_name="India",
            continent="Asia",
            confidence=0.9,
            evidence=(),
            mismatch_reason=None,
        )

    async def fake_social_extract(self, company_name: str, domain: str, **kwargs):
        return {
            "facebook": None,
            "linkedin": None,
            "instagram": None,
            "tiktok": None,
            "social_resolution": {},
        }

    monkeypatch.setattr(leads_module, "_fetch_homepage", fake_fetch_homepage)
    monkeypatch.setattr(leads_module.CompanyNameExtractor, "extract", fake_company_name_extract)
    monkeypatch.setattr(leads_module.CountryDetector, "detect", fake_country_detect)
    monkeypatch.setattr(leads_module.SocialLinksExtractor, "extract", fake_social_extract)

    lead_item = asyncio.run(
        _build_lead_item(
            SearchRuntime(),
            {
                "link": "https://www.facebook.com/apogeeprecisionlaser/posts/123",
                "title": "Apogee Precision Laser",
                "snippet": "Official updates from Apogee Precision Laser",
            },
            {
                "country": "India",
                "keyword": "laser land level",
                "source_type": "social",
                "source_name": "facebook_page",
            },
            "India",
        )
    )

    assert lead_item is not None
    assert lead_item["source_url"] == "https://www.facebook.com/apogeeprecisionlaser"
    assert lead_item["facebook_url"] == "https://www.facebook.com/apogeeprecisionlaser"
    assert lead_item["raw_data"]["social_resolution"]["facebook"]["decision"] == "accepted_recovered_profile"
