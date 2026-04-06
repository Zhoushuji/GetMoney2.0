from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

from sqlalchemy import select

from app.database import SessionLocal
from app.services.extraction.country_detection import resolve_country
from app.models.country_search_source import CountrySearchSource
from app.services.search.social_resolution import classify_social_url
from app.services.search.yellowpages import YELLOW_PAGES


@dataclass(frozen=True)
class SearchSourceDefinition:
    name: str
    source_type: str
    domain: str
    entity_query_templates: tuple[str, ...]
    fallback_query_templates: tuple[str, ...] = ()
    priority: int = 100


GLOBAL_SOCIAL_SOURCES: tuple[SearchSourceDefinition, ...] = (
    SearchSourceDefinition(
        name="linkedin_company",
        source_type="social",
        domain="linkedin.com",
        entity_query_templates=(
            'site:linkedin.com "{keyword}"',
            'site:linkedin.com/company "{keyword}"',
            'site:linkedin.com "{keyword}" "{country}"',
        ),
        priority=80,
    ),
    SearchSourceDefinition(
        name="facebook_page",
        source_type="social",
        domain="facebook.com",
        entity_query_templates=(
            'site:facebook.com "{keyword}"',
            'site:facebook.com "{keyword}" "{country}"',
        ),
        priority=81,
    ),
    SearchSourceDefinition(
        name="instagram_profile",
        source_type="social",
        domain="instagram.com",
        entity_query_templates=(
            'site:instagram.com "{keyword}"',
            'site:instagram.com "{keyword}" "{country}"',
        ),
        priority=82,
    ),
    SearchSourceDefinition(
        name="tiktok_profile",
        source_type="social",
        domain="tiktok.com",
        entity_query_templates=(
            'site:tiktok.com "{keyword}"',
            'site:tiktok.com "{keyword}" "{country}"',
        ),
        priority=83,
    ),
)

COUNTRY_SOURCE_OVERRIDES: dict[str, tuple[SearchSourceDefinition, ...]] = {
    "IN": (
        SearchSourceDefinition(
            name="indiamart",
            source_type="marketplace",
            domain="indiamart.com",
            entity_query_templates=(
                'site:indiamart.com "{keyword}" "profile.html"',
                'site:indiamart.com "{keyword}" "about-us.html"',
                'site:indiamart.com "{keyword}" "manufacturer from"',
                'site:indiamart.com "{keyword}" "supplier from"',
                'site:indiamart.com "{keyword}" "retailer from"',
                'site:indiamart.com "{keyword}" "wholesaler from"',
            ),
            fallback_query_templates=('site:indiamart.com "{keyword}"',),
            priority=10,
        ),
        SearchSourceDefinition(
            name="tradeindia",
            source_type="marketplace",
            domain="tradeindia.com",
            entity_query_templates=(
                'site:tradeindia.com/products "{keyword}"',
                'site:tradeindia.com "{keyword}" "Company Profile"',
                'site:tradeindia.com "{keyword}" "Seller Details"',
                'site:tradeindia.com "{keyword}" "Registered in"',
                'site:tradeindia.com "{keyword}" "Established in"',
                'site:tradeindia.com "{keyword}" "Business Type"',
                'site:tradeindia.com "{keyword}" "View More Products From This Seller"',
            ),
            fallback_query_templates=('site:tradeindia.com "{keyword}"',),
            priority=20,
        ),
        SearchSourceDefinition(
            name="justdial",
            source_type="directory",
            domain="justdial.com",
            entity_query_templates=(
                'site:justdial.com/shop-online "{keyword}"',
                'site:justdial.com/jdmart "{keyword}"',
                'site:justdial.com "{keyword}" "_BZDET"',
                'site:justdial.com "{keyword}" "Get Directions" "Copy Address"',
                'site:justdial.com "{keyword}" "Get Best Quote"',
                'site:justdial.com "{keyword}" "View Catalogue"',
            ),
            fallback_query_templates=('site:justdial.com "{keyword}"',),
            priority=30,
        ),
        SearchSourceDefinition(
            name="exportersindia",
            source_type="marketplace",
            domain="exportersindia.com",
            entity_query_templates=(
                'site:exportersindia.com "{keyword}" "{country}"',
            ),
            fallback_query_templates=('site:exportersindia.com "{keyword}"',),
            priority=40,
        ),
    ),
}

DIRECT_RESULT_PAGE_TYPES = {"homepage", "company_profile", "store_profile", "official_social_page"}
BLOCKED_RESULT_PAGE_TYPES = {
    "directory_home",
    "search_results_page",
    "category_page",
    "aggregator_page",
    "social_post_page",
    "video_page",
    "personal_profile",
}

DIRECT_SOURCE_ENTITY_PRIORITY = {
    "company_profile": 4,
    "store_profile": 3,
    "official_social_page": 2,
    "homepage": 1,
}
GENERIC_DIRECTORY_SEGMENTS = {
    "search",
    "results",
    "categories",
    "category",
    "directory",
    "directories",
    "listing",
    "listings",
    "products",
    "product",
    "seller",
    "sellers",
    "buyers",
    "companies",
    "company",
    "city",
    "state",
}
TRADEINDIA_BLOCKED_SEGMENTS = GENERIC_DIRECTORY_SEGMENTS | {
    "search.html",
    "search",
    "products",
    "sellers",
    "suppliers",
    "manufacturers",
    "manufacturer",
    "exporters",
    "exporter",
    "buyers",
    "categories",
    "city",
    "state",
}
JUSTDIAL_BLOCKED_SEGMENTS = GENERIC_DIRECTORY_SEGMENTS | {
    "businesses",
    "all-businesses",
    "local-search",
    "services",
    "category",
}
EXPORTERSINDIA_BLOCKED_SEGMENTS = GENERIC_DIRECTORY_SEGMENTS | {
    "product-detail",
    "suppliers",
    "manufacturers",
    "manufacturer",
    "supplier",
    "exporters",
    "exporter",
    "buyers",
    "buy",
    "search",
}
MARKETPLACE_GENERIC_TOKEN_WORDS = {
    "agriculture",
    "agricultural",
    "automatic",
    "best",
    "blue",
    "box",
    "buy",
    "control",
    "digital",
    "dns",
    "fine",
    "finish",
    "get",
    "green",
    "guided",
    "horizontal",
    "industrial",
    "land",
    "laser",
    "latest",
    "level",
    "leveler",
    "levelers",
    "leveller",
    "levellers",
    "machine",
    "machines",
    "manufacturers",
    "manufacturer",
    "model",
    "online",
    "price",
    "products",
    "pro",
    "quote",
    "seller",
    "sports",
    "store",
    "supplier",
    "system",
    "systems",
    "top",
    "trader",
    "wholesaler",
}
MARKETPLACE_PRODUCT_TAIL_PATTERN = re.compile(
    r"(?i)(?:[-_\s]*(?:laserland|laser)?[-_\s]*land[-_\s]*level(?:ing|er|ers|eller|ellers|leveller|levellers)(?:[-_\s].*)?)$"
)
_COUNTRY_SOURCE_CACHE: dict[str, dict[str, list[SearchSourceDefinition]]] = {}


def _normalized_country_code(country: str | None) -> str:
    resolved = resolve_country(country)
    if resolved is not None and resolved.code:
        return resolved.code
    return str(country or "").strip().upper()


def _domain_from_template(template: str) -> str | None:
    parsed = urlparse(template)
    host = (parsed.netloc or "").strip().lower()
    if not host:
        return None
    return host.removeprefix("www.")


def _yellow_pages_source(country_code: str) -> SearchSourceDefinition | None:
    template = YELLOW_PAGES.get(country_code.upper())
    if not template:
        return None
    domain = _domain_from_template(template)
    if not domain:
        return None
    return SearchSourceDefinition(
        name=f"{country_code.lower()}_yellow_pages",
        source_type="directory",
        domain=domain,
        entity_query_templates=(f'site:{domain} "{{keyword}}" "{{country}}"',),
        priority=40,
    )


def _source_slug(name: str | None, domain: str | None) -> str:
    tokens = re.findall(r"[a-z0-9]+", str(name or "").strip().lower())
    if tokens:
        return "_".join(tokens)
    return "_".join(re.findall(r"[a-z0-9]+", str(domain or "").strip().lower())) or "source"


def _generic_source_definition(*, name: str, source_type: str, domain: str, priority: int) -> SearchSourceDefinition:
    return SearchSourceDefinition(
        name=name,
        source_type=source_type,
        domain=domain,
        entity_query_templates=(f'site:{domain} "{{keyword}}" "{{country}}"',),
        fallback_query_templates=(f'site:{domain} "{{keyword}}"',),
        priority=priority,
    )


def _definition_from_source_record(record: CountrySearchSource) -> SearchSourceDefinition:
    priority_base = 10 if record.source_type == "marketplace" else 40
    priority = priority_base + max(0, int(record.source_rank) - 1) * 10
    domain = str(record.source_domain or "").strip().lower()
    source_name = _source_slug(record.source_name, domain)
    if domain.endswith("indiamart.com") or source_name == "indiamart":
        return SearchSourceDefinition(
            name="indiamart",
            source_type="marketplace",
            domain="indiamart.com",
            entity_query_templates=(
                'site:indiamart.com "{keyword}" "profile.html"',
                'site:indiamart.com "{keyword}" "about-us.html"',
                'site:indiamart.com "{keyword}" "manufacturer from"',
                'site:indiamart.com "{keyword}" "supplier from"',
                'site:indiamart.com "{keyword}" "retailer from"',
                'site:indiamart.com "{keyword}" "wholesaler from"',
            ),
            fallback_query_templates=('site:indiamart.com "{keyword}"',),
            priority=priority,
        )
    if domain.endswith("tradeindia.com") or source_name == "tradeindia":
        return SearchSourceDefinition(
            name="tradeindia",
            source_type="marketplace",
            domain="tradeindia.com",
            entity_query_templates=(
                'site:tradeindia.com/products "{keyword}"',
                'site:tradeindia.com "{keyword}" "Company Profile"',
                'site:tradeindia.com "{keyword}" "Seller Details"',
                'site:tradeindia.com "{keyword}" "Registered in"',
                'site:tradeindia.com "{keyword}" "Established in"',
                'site:tradeindia.com "{keyword}" "Business Type"',
                'site:tradeindia.com "{keyword}" "View More Products From This Seller"',
            ),
            fallback_query_templates=('site:tradeindia.com "{keyword}"',),
            priority=priority,
        )
    if domain.endswith("justdial.com") or source_name == "justdial":
        return SearchSourceDefinition(
            name="justdial",
            source_type="directory",
            domain="justdial.com",
            entity_query_templates=(
                'site:justdial.com/shop-online "{keyword}"',
                'site:justdial.com/jdmart "{keyword}"',
                'site:justdial.com "{keyword}" "_BZDET"',
                'site:justdial.com "{keyword}" "Get Directions" "Copy Address"',
                'site:justdial.com "{keyword}" "Get Best Quote"',
                'site:justdial.com "{keyword}" "View Catalogue"',
            ),
            fallback_query_templates=('site:justdial.com "{keyword}"',),
            priority=priority,
        )
    return _generic_source_definition(
        name=source_name,
        source_type=record.source_type,
        domain=domain,
        priority=priority,
    )


def _default_country_source_bucket(country_code: str) -> dict[str, list[SearchSourceDefinition]]:
    directory_sources: list[SearchSourceDefinition] = []
    yellow_pages = _yellow_pages_source(country_code)
    if yellow_pages is not None:
        directory_sources.append(yellow_pages)

    marketplace_sources: list[SearchSourceDefinition] = []
    for source in COUNTRY_SOURCE_OVERRIDES.get(country_code, ()):
        if source.source_type == "directory":
            directory_sources.append(source)
        else:
            marketplace_sources.append(source)
    directory_sources.sort(key=lambda item: item.priority)
    marketplace_sources.sort(key=lambda item: item.priority)
    return {
        "directory_sources": directory_sources,
        "marketplace_sources": marketplace_sources,
    }


def _current_source_bucket(country_code: str) -> dict[str, list[SearchSourceDefinition]]:
    bucket = _COUNTRY_SOURCE_CACHE.get(country_code)
    if bucket:
        return {
            "directory_sources": list(bucket.get("directory_sources") or []),
            "marketplace_sources": list(bucket.get("marketplace_sources") or []),
        }
    return _default_country_source_bucket(country_code)


async def load_country_search_source_cache() -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(CountrySearchSource).order_by(
                CountrySearchSource.country_code.asc(),
                CountrySearchSource.source_type.asc(),
                CountrySearchSource.source_rank.asc(),
            )
        )
        rows = list(result.scalars())
    cache: dict[str, dict[str, list[SearchSourceDefinition]]] = {}
    for row in rows:
        bucket = cache.setdefault(
            row.country_code,
            {"directory_sources": [], "marketplace_sources": []},
        )
        definition = _definition_from_source_record(row)
        key = "directory_sources" if definition.source_type == "directory" else "marketplace_sources"
        bucket[key].append(definition)
    for bucket in cache.values():
        bucket["directory_sources"].sort(key=lambda item: item.priority)
        bucket["marketplace_sources"].sort(key=lambda item: item.priority)
    _COUNTRY_SOURCE_CACHE.clear()
    _COUNTRY_SOURCE_CACHE.update(cache)


def resolve_country_search_sources(country: str | None) -> dict[str, object]:
    country_code = _normalized_country_code(country)
    bucket = _current_source_bucket(country_code)

    return {
        "country_code": country_code,
        "directory_sources": bucket["directory_sources"],
        "marketplace_sources": bucket["marketplace_sources"],
        "social_sources": list(GLOBAL_SOCIAL_SOURCES),
    }


def resolve_directory_source_names(countries: list[str]) -> dict[str, dict[str, list[str]]]:
    resolved: dict[str, dict[str, list[str]]] = {}
    for country in countries:
        country_sources = resolve_country_search_sources(country)
        country_code = str(country_sources["country_code"])
        resolved[country_code] = {
            "directories": [item.name for item in country_sources["directory_sources"]],
            "marketplaces": [item.name for item in country_sources["marketplace_sources"]],
            "socials": [item.name for item in country_sources["social_sources"]],
        }
    return resolved


def _host_matches(url: str, domain: str) -> bool:
    host = (urlparse(url).netloc or "").strip().lower().removeprefix("www.")
    return bool(host) and (host == domain or host.endswith(f".{domain}"))


def match_source_definition(url: str) -> SearchSourceDefinition | None:
    for definition in GLOBAL_SOCIAL_SOURCES:
        if _host_matches(url, definition.domain):
            return definition
    for bucket in _COUNTRY_SOURCE_CACHE.values():
        for definition in [*(bucket.get("directory_sources") or []), *(bucket.get("marketplace_sources") or [])]:
            if _host_matches(url, definition.domain):
                return definition
    for definitions in COUNTRY_SOURCE_OVERRIDES.values():
        for definition in definitions:
            if _host_matches(url, definition.domain):
                return definition
    for template in YELLOW_PAGES.values():
        domain = _domain_from_template(template)
        if domain and _host_matches(url, domain):
            return SearchSourceDefinition(
                name=f"{domain}_directory",
                source_type="directory",
                domain=domain,
                entity_query_templates=(f'site:{domain} "{{keyword}}" "{{country}}"',),
                priority=40,
            )
    return None


def direct_result_page_priority(page_type: str | None) -> int:
    return DIRECT_SOURCE_ENTITY_PRIORITY.get(str(page_type or "").strip().lower(), 0)


def _sanitize_entity_token(value: str | None) -> str:
    parts = re.findall(r"[a-z0-9]+", str(value or "").strip().lower())
    return "-".join(parts)


def _humanize_entity_token(value: str | None) -> str | None:
    token = _sanitize_entity_token(value)
    if not token:
        return None
    return " ".join(part.capitalize() for part in token.split("-") if part)


def _all_words_generic(value: str | None) -> bool:
    words = re.findall(r"[a-z0-9]+", str(value or "").strip().lower())
    return bool(words) and all(word in MARKETPLACE_GENERIC_TOKEN_WORDS for word in words)


def _clean_company_slug(value: str | None, *, strip_product_tail: bool) -> str | None:
    candidate = str(value or "").strip().strip("/")
    if not candidate:
        return None
    candidate = re.sub(r"(?i)\.html$", "", candidate)
    candidate = re.sub(r"(?i)^(?:m-s|ms|m/s)[-_ ]*", "", candidate).strip(" -_")
    candidate = re.sub(r"(?:-\d+)+$", "", candidate).strip(" -_")
    if strip_product_tail:
        candidate = MARKETPLACE_PRODUCT_TAIL_PATTERN.sub("", candidate).strip(" -_")
    token = _sanitize_entity_token(candidate)
    if not token or _all_words_generic(token):
        return None
    return token


def _meaningful_segments(segments: list[str], blocked_segments: set[str]) -> list[str]:
    meaningful: list[str] = []
    for segment in segments:
        normalized = segment.lower().strip()
        if not normalized or normalized in blocked_segments:
            continue
        if normalized.endswith(".html") and normalized not in blocked_segments:
            normalized = normalized[:-5]
        if normalized.isdigit():
            continue
        meaningful.append(normalized)
    return meaningful


def _indiamart_entity_token(host: str, segments: list[str]) -> str | None:
    if host.startswith(("dir.", "m.", "my.", "pdf.", "catalogs.")):
        return None
    if not segments:
        return None
    if segments[0] == "company" and len(segments) >= 2 and segments[1].isdigit():
        return f"company-{segments[1]}"
    if segments[0] == "proddetail":
        return None
    meaningful = _meaningful_segments(segments, GENERIC_DIRECTORY_SEGMENTS)
    return meaningful[0] if meaningful else None


def _tradeindia_entity_token(segments: list[str]) -> str | None:
    if not segments:
        return None
    if segments[0] == "products":
        return None
    meaningful = _meaningful_segments(segments, TRADEINDIA_BLOCKED_SEGMENTS)
    return _clean_company_slug(meaningful[0], strip_product_tail=False) if meaningful else None


def _justdial_entity_token(segments: list[str]) -> str | None:
    if not segments:
        return None
    if segments[0] == "shop-online":
        if len(segments) >= 2:
            return _clean_company_slug(segments[1], strip_product_tail=True)
    if segments[0] == "jdmart" and len(segments) >= 3:
        return _clean_company_slug(segments[2], strip_product_tail=True)
    if segments[-1].endswith("_bzdet") and len(segments) >= 2:
        return _clean_company_slug(segments[-2], strip_product_tail=True)
    if any(segment.startswith("nct-") for segment in segments):
        return None
    meaningful = _meaningful_segments(segments, JUSTDIAL_BLOCKED_SEGMENTS)
    if len(meaningful) < 2:
        return None
    return _clean_company_slug(meaningful[-1], strip_product_tail=True)


def _exportersindia_entity_token(segments: list[str]) -> str | None:
    if not segments:
        return None
    if segments[0] == "product-detail":
        return None
    meaningful = _meaningful_segments(segments, EXPORTERSINDIA_BLOCKED_SEGMENTS)
    if not meaningful:
        return None
    if len(segments) == 1:
        return _clean_company_slug(meaningful[0], strip_product_tail=False)
    return None


def source_entity_token(url: str, *, source_name: str | None, source_type: str | None) -> str | None:
    parsed = urlparse(url)
    host = (parsed.netloc or "").strip().lower().removeprefix("www.")
    segments = [segment for segment in (parsed.path or "/").lower().split("/") if segment]
    if source_type == "social":
        if source_name == "linkedin_company" and len(segments) >= 2 and segments[0] == "company":
            return _sanitize_entity_token(segments[1])
        if source_name == "facebook_page" and segments:
            return _sanitize_entity_token(segments[0])
        if source_name == "instagram_profile" and segments:
            return _sanitize_entity_token(segments[0])
        if source_name == "tiktok_profile" and segments and segments[0].startswith("@"):
            return _sanitize_entity_token(segments[0].removeprefix("@"))
        return None
    if source_name == "indiamart":
        return _sanitize_entity_token(_indiamart_entity_token(host, segments))
    if source_name == "tradeindia":
        return _sanitize_entity_token(_tradeindia_entity_token(segments))
    if source_name == "justdial":
        return _sanitize_entity_token(_justdial_entity_token(segments))
    if source_name == "exportersindia":
        return _sanitize_entity_token(_exportersindia_entity_token(segments))
    meaningful = _meaningful_segments(segments, GENERIC_DIRECTORY_SEGMENTS)
    return _sanitize_entity_token(meaningful[0] if meaningful else None)


def source_entity_label(url: str, *, source_name: str | None, source_type: str | None) -> str | None:
    return _humanize_entity_token(source_entity_token(url, source_name=source_name, source_type=source_type))


def build_source_entity_key(
    url: str,
    *,
    source_name: str | None,
    source_type: str | None,
    company_name: str | None = None,
    country: str | None = None,
) -> str | None:
    normalized_company = _sanitize_entity_token(company_name)
    normalized_country = _sanitize_entity_token(country)
    token = source_entity_token(url, source_name=source_name, source_type=source_type)
    if token and source_name:
        if source_name in {"tradeindia", "justdial"} and normalized_country:
            return f"{source_name}:{normalized_country}:{token}"
        return f"{source_name}:{token}"
    if source_name in {"tradeindia", "justdial"} and normalized_company in {"unknown-company", "product-detail", "best-deals"}:
        normalized_company = None
    if source_name in {"tradeindia", "justdial"} and normalized_company and source_name and normalized_country:
        return f"{source_name}:{normalized_country}:{normalized_company}"
    if source_name in {"tradeindia", "justdial"} and normalized_company and source_name:
        return f"{source_name}:{normalized_company}"
    if normalized_company and source_name and normalized_country:
        return f"{source_name}:{normalized_country}:{normalized_company}"
    if normalized_company and source_name:
        return f"{source_name}:{normalized_company}"
    return None


def classify_result_page(url: str, *, source_name: str | None, source_type: str | None) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or "").strip().lower().removeprefix("www.")
    path = parsed.path or "/"
    lowered_path = path.lower()
    segments = [segment for segment in lowered_path.split("/") if segment]

    if source_type == "social":
        return classify_social_url(url).page_type

    if source_type in {"directory", "marketplace"}:
        if source_name == "indiamart":
            if host.startswith(("dir.", "m.", "my.", "pdf.", "catalogs.")):
                return "aggregator_page"
        if not segments:
            return "directory_home"
        query_text = (parsed.query or "").lower()
        if any(part in {"search", "results", "categories", "directory", "directories", "listing", "listings"} for part in segments):
            return "search_results_page"
        if source_name == "indiamart":
            if lowered_path.endswith("/profile.html") or lowered_path.endswith("/about-us.html"):
                return "company_profile"
            if segments and segments[0] == "company" and len(segments) >= 2 and segments[1].isdigit():
                return "company_profile"
            if "/proddetail/" in lowered_path:
                return "aggregator_page"
            if len(segments) == 1 and segments[0] not in {"search", "products", "category", "seller"}:
                return "store_profile"
            if lowered_path.endswith(".html") and len(segments) >= 2:
                return "store_profile"
            return "aggregator_page"
        if source_name == "tradeindia":
            if host.startswith(("dir.", "m.", "catalogs.")):
                return "aggregator_page"
            if query_text:
                return "search_results_page"
            if segments and segments[0] == "products":
                return "store_profile" if lowered_path.endswith(".html") else "search_results_page"
            if any(segment in TRADEINDIA_BLOCKED_SEGMENTS for segment in segments):
                return "search_results_page"
            meaningful = _meaningful_segments(segments, TRADEINDIA_BLOCKED_SEGMENTS)
            if not meaningful:
                return "directory_home"
            if len(meaningful) == 1 and re.fullmatch(r".*-\d+", meaningful[0]):
                return "company_profile"
            return "search_results_page"
        if source_name == "justdial":
            if query_text:
                return "search_results_page"
            if segments and segments[0] == "india":
                return "search_results_page"
            if segments and segments[0] == "shop-online":
                return "store_profile" if len(segments) >= 2 else "search_results_page"
            if segments and segments[0] == "jdmart":
                return "store_profile" if any("-ent-" in segment or segment.startswith("pid-") for segment in segments) else "search_results_page"
            if segments and segments[-1].endswith("_bzdet"):
                return "company_profile" if len(segments) >= 3 else "search_results_page"
            if any(segment.startswith("nct-") for segment in segments):
                return "search_results_page"
            if any(segment in JUSTDIAL_BLOCKED_SEGMENTS for segment in segments):
                return "search_results_page"
            return "search_results_page"
        if source_name == "exportersindia":
            if host.startswith(("dir.", "m.", "catalogs.")):
                return "aggregator_page"
            if query_text:
                return "search_results_page"
            if segments and segments[0] == "product-detail":
                return "store_profile" if len(segments) >= 2 and lowered_path.endswith(".htm") else "search_results_page"
            if len(segments) == 1 and not segments[0].endswith(".htm"):
                return "company_profile"
            if len(segments) == 2 and lowered_path.endswith(".htm"):
                return "listing_page"
            if any(segment in EXPORTERSINDIA_BLOCKED_SEGMENTS for segment in segments):
                return "search_results_page"
            return "search_results_page"
        return "company_profile" if len(segments) >= 1 else "directory_home"

    if not segments:
        return "homepage"
    if len(segments) == 1:
        return "homepage"
    return "company_profile"


def is_direct_result_page(url: str, *, source_name: str | None, source_type: str | None) -> bool:
    page_type = classify_result_page(url, source_name=source_name, source_type=source_type)
    return page_type in DIRECT_RESULT_PAGE_TYPES
