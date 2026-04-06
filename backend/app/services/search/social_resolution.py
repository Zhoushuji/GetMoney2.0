from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import re
from urllib.parse import urlparse

INVALID_SOCIAL_PAGE_TYPES = {"search_results_page", "aggregator_page"}
OFFICIAL_SOCIAL_PAGE_TYPES = {"official_social_page"}
ALLOWED_SOCIAL_DOMAINS = {
    "facebook": {"facebook.com", "m.facebook.com"},
    "linkedin": {"linkedin.com", "in.linkedin.com"},
    "tiktok": {"tiktok.com"},
    "instagram": {"instagram.com"},
}

SOCIAL_TYPE_BONUS = {
    "fb_page": 0.20,
    "fb_profile": 0.18,
    "fb_group": 0.06,
    "fb_event": 0.03,
    "fb_post": 0.05,
    "fb_video": 0.05,
    "li_company": 0.20,
    "li_company_sub": 0.12,
    "li_person": 0.05,
    "li_post": 0.04,
    "tt_profile": 0.20,
    "tt_profile_sub": 0.10,
    "tt_video": 0.08,
    "ig_profile": 0.20,
    "ig_post": 0.04,
    "ig_reel": 0.04,
    "ig_post_with_user": 0.08,
    "ig_reel_with_user": 0.08,
    "ig_story": 0.06,
}
STRUCTURAL_INVALID_TYPES = {
    "fb_search",
    "fb_invalid",
    "li_job",
    "li_school",
    "li_search",
    "tt_discover",
    "tt_hashtag",
    "tt_invalid",
    "ig_explore",
    "ig_invalid",
}
LEGAL_SUFFIXES = {
    "co",
    "company",
    "corp",
    "corporation",
    "group",
    "inc",
    "industries",
    "industry",
    "limited",
    "llc",
    "llp",
    "ltd",
    "official",
    "private",
    "pvt",
    "solutions",
}
TITLE_SPLIT_PATTERN = re.compile(r"\s*(?:\||-|·|•)\s*")
TEXT_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class SocialUrlClassification:
    platform: str
    specific_type: str
    page_type: str
    identifier: str = ""
    priority: int = 99

    @property
    def is_structurally_invalid(self) -> bool:
        return self.specific_type in STRUCTURAL_INVALID_TYPES or self.page_type in INVALID_SOCIAL_PAGE_TYPES


@dataclass(frozen=True)
class SocialResolution:
    platform: str
    original_url: str
    original_page_type: str
    original_specific_type: str
    recovered_profile_url: str | None
    recovered_page_type: str | None
    official_profile_url: str | None
    selected_url: str | None
    selected_page_type: str | None
    score: float
    decision: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _normalized_company_text(value: str | None) -> str:
    words = [
        token
        for token in TEXT_TOKEN_PATTERN.findall(str(value or "").lower().replace("&", " "))
        if token not in LEGAL_SUFFIXES
    ]
    return " ".join(words)


def _compact_text(value: str | None) -> str:
    return "".join(TEXT_TOKEN_PATTERN.findall(_normalized_company_text(value)))


def _domain_text(value: str | None) -> str:
    parsed = urlparse(str(value or ""))
    host = (parsed.netloc or parsed.path or "").strip().lower().removeprefix("www.")
    return host.split(":", 1)[0]


def _host_allowed_for_platform(domain: str, platform: str) -> bool:
    allowed = ALLOWED_SOCIAL_DOMAINS.get(platform, set())
    return domain in allowed


def _text_similarity(left: str | None, right: str | None) -> float:
    a = _compact_text(left)
    b = _compact_text(right)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _contains_company_name(company_name: str | None, haystack: str | None) -> bool:
    company_tokens = _normalized_company_text(company_name)
    searchable = _normalized_company_text(haystack)
    return bool(company_tokens and searchable and company_tokens in searchable)


def _extract_at_handle(text: str | None) -> str | None:
    match = re.search(r"@([a-zA-Z0-9._]{2,64})", str(text or ""))
    return match.group(1) if match else None


def _clean_identifier(value: str | None) -> str:
    identifier = str(value or "").strip().strip("/")
    if not identifier:
        return ""
    return identifier.replace("-", " ").replace("_", " ").strip()


def build_company_social_queries(company_name: str, *, product: str | None = None, country: str | None = None) -> dict[str, list[str]]:
    normalized_company = " ".join(str(company_name or "").split()).strip()
    normalized_product = " ".join(str(product or "").split()).strip()
    normalized_country = " ".join(str(country or "").split()).strip()

    def _queries(prefix: str) -> list[str]:
        queries = [f'site:{prefix} "{normalized_company}"']
        if normalized_country:
            queries.append(f'site:{prefix} "{normalized_company}" {normalized_country}')
        if normalized_product:
            queries.append(f'site:{prefix} "{normalized_company}" {normalized_product}')
        return queries

    return {
        "facebook": _queries("facebook.com"),
        "linkedin": [
            f'site:linkedin.com "{normalized_company}"',
            f'site:linkedin.com/company "{normalized_company}"',
            *( [f'site:linkedin.com "{normalized_company}" {normalized_country}'] if normalized_country else [] ),
        ],
        "tiktok": _queries("tiktok.com"),
        "instagram": _queries("instagram.com"),
    }


def classify_social_url(url: str) -> SocialUrlClassification:
    parsed = urlparse(str(url or ""))
    domain = (parsed.netloc or "").strip().lower().removeprefix("www.")
    path = parsed.path.strip("/")

    if "facebook.com" in domain:
        if not _host_allowed_for_platform(domain, "facebook"):
            return SocialUrlClassification("facebook", "fb_invalid", "aggregator_page")
        if any(fragment in path for fragment in ("sharer.php", "dialog/", "login", "plugins")) or path.startswith("search/"):
            return SocialUrlClassification("facebook", "fb_search", "search_results_page")
        page_match = re.match(r"^pages/([^/]+)/(\d+)$", path)
        if page_match:
            return SocialUrlClassification("facebook", "fb_page", "official_social_page", _clean_identifier(page_match.group(1)), 1)
        if re.match(r"^[^/]+$", path) and "." not in path:
            return SocialUrlClassification("facebook", "fb_profile", "official_social_page", _clean_identifier(path), 2)
        if path.startswith("groups/"):
            group = path.split("/", 2)[1] if len(path.split("/", 2)) > 1 else ""
            return SocialUrlClassification("facebook", "fb_group", "social_group_page", _clean_identifier(group), 4)
        if path.startswith("events/"):
            return SocialUrlClassification("facebook", "fb_event", "social_event_page", "", 5)
        if path.startswith("videos/") or "/videos/" in path or path.startswith("watch/"):
            account = path.split("/videos/")[0].lstrip("/") if "/videos/" in path else ""
            return SocialUrlClassification("facebook", "fb_video", "video_page", _clean_identifier(account), 6)
        if path.startswith("posts/") or "/posts/" in path:
            account = path.split("/posts/")[0].lstrip("/")
            return SocialUrlClassification("facebook", "fb_post", "social_post_page", _clean_identifier(account), 6)
        return SocialUrlClassification("facebook", "fb_other", "aggregator_page", _clean_identifier(path.split("/", 1)[0]), 7)

    if "linkedin.com" in domain:
        if not _host_allowed_for_platform(domain, "linkedin"):
            return SocialUrlClassification("linkedin", "li_invalid", "aggregator_page")
        if path.startswith("search/"):
            return SocialUrlClassification("linkedin", "li_search", "search_results_page")
        company_match = re.match(r"^company/([^/]+)/?$", path)
        if company_match:
            return SocialUrlClassification("linkedin", "li_company", "official_social_page", _clean_identifier(company_match.group(1)), 1)
        company_sub_match = re.match(r"^company/([^/]+)/.+", path)
        if company_sub_match:
            return SocialUrlClassification("linkedin", "li_company_sub", "social_subpage", _clean_identifier(company_sub_match.group(1)), 3)
        if path.startswith("in/"):
            slug = path.split("/", 2)[1] if len(path.split("/", 2)) > 1 else ""
            return SocialUrlClassification("linkedin", "li_person", "personal_profile", _clean_identifier(slug), 4)
        if path.startswith("jobs/"):
            return SocialUrlClassification("linkedin", "li_job", "aggregator_page", "", 5)
        if path.startswith("posts/") or "/posts/" in path:
            return SocialUrlClassification("linkedin", "li_post", "social_post_page", "", 6)
        if path.startswith("school/"):
            return SocialUrlClassification("linkedin", "li_school", "aggregator_page", "", 7)
        return SocialUrlClassification("linkedin", "li_other", "aggregator_page", _clean_identifier(path.split("/", 1)[0]), 8)

    if "tiktok.com" in domain:
        if not _host_allowed_for_platform(domain, "tiktok"):
            return SocialUrlClassification("tiktok", "tt_invalid", "aggregator_page")
        direct_match = re.match(r"^@([^/]+)$", path)
        if direct_match:
            return SocialUrlClassification("tiktok", "tt_profile", "official_social_page", _clean_identifier(direct_match.group(1)), 1)
        video_match = re.match(r"^@([^/]+)/video/", path)
        if video_match:
            return SocialUrlClassification("tiktok", "tt_video", "video_page", _clean_identifier(video_match.group(1)), 3)
        profile_sub_match = re.match(r"^@([^/]+)/.+", path)
        if profile_sub_match:
            return SocialUrlClassification("tiktok", "tt_profile_sub", "social_subpage", _clean_identifier(profile_sub_match.group(1)), 2)
        if path.startswith("tag/"):
            return SocialUrlClassification("tiktok", "tt_hashtag", "aggregator_page", "", 8)
        if path.startswith("discover"):
            return SocialUrlClassification("tiktok", "tt_discover", "search_results_page", "", 9)
        return SocialUrlClassification("tiktok", "tt_other", "aggregator_page", _clean_identifier(path.split("/", 1)[0]), 7)

    if "instagram.com" in domain:
        if not _host_allowed_for_platform(domain, "instagram"):
            return SocialUrlClassification("instagram", "ig_invalid", "aggregator_page")
        if not path:
            return SocialUrlClassification("instagram", "ig_invalid", "aggregator_page")
        profile_match = re.match(r"^([^/]+)/?$", path)
        if profile_match and profile_match.group(1) not in {"p", "reel", "stories", "explore", "tv"}:
            return SocialUrlClassification("instagram", "ig_profile", "official_social_page", _clean_identifier(profile_match.group(1)), 1)
        post_with_user = re.match(r"^([^/]+)/p/", path)
        if post_with_user:
            return SocialUrlClassification("instagram", "ig_post_with_user", "social_post_page", _clean_identifier(post_with_user.group(1)), 4)
        reel_with_user = re.match(r"^([^/]+)/reel/", path)
        if reel_with_user:
            return SocialUrlClassification("instagram", "ig_reel_with_user", "video_page", _clean_identifier(reel_with_user.group(1)), 4)
        if path.startswith("p/"):
            return SocialUrlClassification("instagram", "ig_post", "social_post_page", "", 5)
        if path.startswith("reel/"):
            return SocialUrlClassification("instagram", "ig_reel", "video_page", "", 5)
        if path.startswith("stories/"):
            story_identifier = path.split("/", 2)[1] if len(path.split("/", 2)) > 1 else ""
            return SocialUrlClassification("instagram", "ig_story", "social_post_page", _clean_identifier(story_identifier), 4)
        if path.startswith("explore/"):
            return SocialUrlClassification("instagram", "ig_explore", "search_results_page", "", 9)
        return SocialUrlClassification("instagram", "ig_other", "aggregator_page", _clean_identifier(path.split("/", 1)[0]), 7)

    return SocialUrlClassification("unknown", "unknown", "aggregator_page")


def recover_social_profile_url(
    url: str,
    classification: SocialUrlClassification,
    *,
    title: str | None = None,
    snippet: str | None = None,
) -> str | None:
    identifier = classification.identifier
    if classification.platform == "facebook" and identifier:
        return f"https://www.facebook.com/{identifier.replace(' ', '-')}"
    if classification.platform == "linkedin" and identifier:
        if classification.specific_type in {"li_company", "li_company_sub"}:
            return f"https://www.linkedin.com/company/{identifier.replace(' ', '-')}"
        if classification.specific_type == "li_person":
            return f"https://www.linkedin.com/in/{identifier.replace(' ', '-')}"
    if classification.platform == "tiktok" and identifier:
        return f"https://www.tiktok.com/@{identifier.replace(' ', '')}"
    if classification.platform == "instagram" and identifier:
        return f"https://www.instagram.com/{identifier.replace(' ', '')}/"

    combined = " ".join(part for part in [title, snippet] if part)
    recovered_handle = _extract_at_handle(combined)
    if classification.platform == "tiktok" and recovered_handle:
        return f"https://www.tiktok.com/@{recovered_handle}"
    if classification.platform == "instagram" and recovered_handle:
        return f"https://www.instagram.com/{recovered_handle}/"
    return None


def score_social_result(
    company_name: str | None,
    url: str,
    result: dict,
    classification: SocialUrlClassification,
    *,
    known_domain: str | None = None,
) -> float:
    title = str(result.get("title") or "")
    snippet = str(result.get("snippet") or "")
    identifier = classification.identifier
    score = SOCIAL_TYPE_BONUS.get(classification.specific_type, 0.02)

    if identifier and company_name:
        score += _text_similarity(company_name, identifier) * 0.35

    if company_name:
        if _contains_company_name(company_name, title):
            score += 0.20
        else:
            score += _text_similarity(company_name, title) * 0.15
        if _contains_company_name(company_name, snippet):
            score += 0.10

    normalized_known_domain = str(known_domain or "").strip().lower().removeprefix("www.")
    searchable = " ".join(
        part.lower()
        for part in [title, snippet, _domain_text(url)]
        if part
    )
    if normalized_known_domain and normalized_known_domain in searchable:
        score += 0.15

    return min(score, 1.0)


def _strong_identity_match(
    company_name: str | None,
    classification: SocialUrlClassification,
    *,
    title: str | None = None,
    snippet: str | None = None,
    known_domain: str | None = None,
) -> bool:
    if not company_name:
        return False
    identifier_similarity = _text_similarity(company_name, classification.identifier)
    title_similarity = _text_similarity(company_name, title)
    snippet_similarity = _text_similarity(company_name, snippet)
    contains_in_title = _contains_company_name(company_name, title)
    contains_in_snippet = _contains_company_name(company_name, snippet)
    normalized_known_domain = str(known_domain or "").strip().lower().removeprefix("www.")
    searchable = " ".join(
        part.lower()
        for part in [str(title or ""), str(snippet or ""), _domain_text(classification.identifier)]
        if part
    )
    known_domain_match = bool(normalized_known_domain and normalized_known_domain in searchable)

    if identifier_similarity >= 0.60:
        return True
    if known_domain_match and (contains_in_title or contains_in_snippet or identifier_similarity >= 0.35):
        return True
    if classification.page_type in OFFICIAL_SOCIAL_PAGE_TYPES:
        if identifier_similarity >= 0.55 and (contains_in_title or contains_in_snippet or title_similarity >= 0.50):
            return True
    return contains_in_title and contains_in_snippet and max(title_similarity, snippet_similarity) >= 0.90


def resolve_social_result(
    *,
    company_name: str | None,
    result: dict,
    known_domain: str | None = None,
) -> SocialResolution:
    url = str(result.get("link") or "").strip()
    classification = classify_social_url(url)
    recovered_profile_url = recover_social_profile_url(
        url,
        classification,
        title=str(result.get("title") or ""),
        snippet=str(result.get("snippet") or ""),
    )
    recovered_page_type = None
    official_profile_url = None
    if recovered_profile_url:
        recovered_classification = classify_social_url(recovered_profile_url)
        recovered_page_type = recovered_classification.page_type
        if recovered_classification.page_type in OFFICIAL_SOCIAL_PAGE_TYPES:
            official_profile_url = recovered_profile_url
    if classification.page_type in OFFICIAL_SOCIAL_PAGE_TYPES:
        official_profile_url = url
    title = str(result.get("title") or "")
    snippet = str(result.get("snippet") or "")

    score = score_social_result(company_name, url, result, classification, known_domain=known_domain)

    if classification.is_structurally_invalid:
        return SocialResolution(
            platform=classification.platform,
            original_url=url,
            original_page_type=classification.page_type,
            original_specific_type=classification.specific_type,
            recovered_profile_url=recovered_profile_url,
            recovered_page_type=recovered_page_type,
            official_profile_url=official_profile_url,
            selected_url=None,
            selected_page_type=None,
            score=score,
            decision="rejected_structural",
        )

    official_identity_match = False
    if official_profile_url:
        official_classification = classify_social_url(official_profile_url)
        official_identity_match = _strong_identity_match(
            company_name,
            official_classification,
            title=title,
            snippet=snippet,
            known_domain=known_domain,
        )

    if classification.page_type in OFFICIAL_SOCIAL_PAGE_TYPES and score >= 0.45 and official_identity_match:
        return SocialResolution(
            platform=classification.platform,
            original_url=url,
            original_page_type=classification.page_type,
            original_specific_type=classification.specific_type,
            recovered_profile_url=recovered_profile_url,
            recovered_page_type=recovered_page_type,
            official_profile_url=official_profile_url,
            selected_url=url,
            selected_page_type=classification.page_type,
            score=score,
            decision="accepted_direct_profile",
        )

    if official_profile_url and score >= 0.45 and official_identity_match:
        return SocialResolution(
            platform=classification.platform,
            original_url=url,
            original_page_type=classification.page_type,
            original_specific_type=classification.specific_type,
            recovered_profile_url=recovered_profile_url,
            recovered_page_type=recovered_page_type,
            official_profile_url=official_profile_url,
            selected_url=official_profile_url,
            selected_page_type="official_social_page",
            score=score,
            decision="accepted_recovered_profile",
        )

    if score >= 0.70:
        return SocialResolution(
            platform=classification.platform,
            original_url=url,
            original_page_type=classification.page_type,
            original_specific_type=classification.specific_type,
            recovered_profile_url=recovered_profile_url,
            recovered_page_type=recovered_page_type,
            official_profile_url=official_profile_url,
            selected_url=url,
            selected_page_type=classification.page_type,
            score=score,
            decision="accepted_direct_high_score",
        )

    return SocialResolution(
        platform=classification.platform,
        original_url=url,
        original_page_type=classification.page_type,
        original_specific_type=classification.specific_type,
        recovered_profile_url=recovered_profile_url,
        recovered_page_type=recovered_page_type,
        official_profile_url=official_profile_url,
        selected_url=None,
        selected_page_type=None,
        score=score,
        decision="rejected_low_score",
    )


def choose_best_social_resolution(
    company_name: str | None,
    *,
    platform: str,
    results: list[dict],
    known_domain: str | None = None,
) -> SocialResolution | None:
    candidates: list[SocialResolution] = []
    for result in results:
        resolution = resolve_social_result(company_name=company_name, result=result, known_domain=known_domain)
        if resolution.platform != platform or resolution.selected_url is None:
            continue
        candidates.append(resolution)
    if not candidates:
        return None

    def _sort_key(item: SocialResolution) -> tuple[int, float]:
        decision_rank = {
            "accepted_direct_profile": 0,
            "accepted_recovered_profile": 1,
            "accepted_direct_high_score": 2,
        }.get(item.decision, 9)
        return (decision_rank, -item.score)

    candidates.sort(key=_sort_key)
    return candidates[0]
