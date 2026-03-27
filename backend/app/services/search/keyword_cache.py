from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from app.services.extraction.country_detection import country_gl, preferred_country_search_term, resolve_country

PRIMARY_QUERY_TEMPLATES = (
    "{keyword} supplier in {country}",
    "{keyword} manufacturer in {country}",
    "{keyword} company in {country}",
)
SECONDARY_QUERY_TEMPLATES = (
    "{keyword} factory in {country}",
    "{keyword} exporter in {country}",
    "{keyword} wholesaler in {country}",
)
ALL_QUERY_TEMPLATES = PRIMARY_QUERY_TEMPLATES + SECONDARY_QUERY_TEMPLATES
SEARCH_STRATEGY_VERSION = "v1"
REFRESH_INTERVAL_DAYS = 90


def normalize_keyword(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split()).strip().lower()


def normalize_keywords(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        normalized_raw = str(raw or "").replace("，", ",").replace("\n", ",")
        for part in normalized_raw.split(","):
            keyword = " ".join(part.split()).strip()
            normalized = normalize_keyword(keyword)
            if not keyword or not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(keyword)
    return ordered


def canonical_domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    host = (parsed.netloc or parsed.path or "").strip().lower()
    if not host:
        return None
    if "@" in host:
        host = host.split("@", 1)[-1]
    if ":" in host:
        host = host.split(":", 1)[0]
    return host.removeprefix("www.") or None


def scope_fingerprint(*, countries: list[str], languages: list[str]) -> str:
    country_codes = []
    for country in countries:
        resolved = resolve_country(country)
        country_codes.append((resolved.code if resolved is not None else str(country or "").strip().upper()) or "")
    payload = {
        "countries": sorted(filter(None, country_codes)),
        "languages": sorted(filter(None, [str(language or "").strip().lower() for language in languages])),
        "strategy": SEARCH_STRATEGY_VERSION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def next_refresh_at(reference: datetime | None = None) -> datetime:
    base = reference or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base + timedelta(days=REFRESH_INTERVAL_DAYS)


def build_keyword_queries(
    keyword: str,
    *,
    countries: list[str],
    languages: list[str],
    stage: int,
) -> list[dict[str, str | int]]:
    templates = PRIMARY_QUERY_TEMPLATES if stage == 1 else SECONDARY_QUERY_TEMPLATES
    query_items: list[dict[str, str | int]] = []
    target_countries = countries or [""]
    target_languages = languages or ["en"]
    for country in target_countries:
        for language in target_languages:
            country_term = preferred_country_search_term(country, language) or str(country or "").strip()
            gl = country_gl(country)
            for template_index, template in enumerate(templates):
                if country_term:
                    query = template.format(keyword=keyword, country=country_term).strip()
                else:
                    query = template.replace(" in {country}", "").format(keyword=keyword, country="").strip()
                query_items.append(
                    {
                        "query": query,
                        "query_key": f"s{stage}:{template_index}:{gl}:{language}:{country_term.lower()}",
                        "country": country,
                        "gl": gl,
                        "language": language,
                        "stage": stage,
                    }
                )
    return query_items
