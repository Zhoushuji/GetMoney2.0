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
    "{keyword} dealer in {country}",
    "{keyword} distributor in {country}",
)
SECONDARY_QUERY_TEMPLATES = (
    "{keyword} factory in {country}",
    "{keyword} exporter in {country}",
    "{keyword} wholesaler in {country}",
    "{keyword} trader in {country}",
    "{keyword} equipment in {country}",
)
ALL_QUERY_TEMPLATES = PRIMARY_QUERY_TEMPLATES + SECONDARY_QUERY_TEMPLATES
SEARCH_STRATEGY_VERSION = "v6"
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


def secondary_official_language(country: str | None) -> str | None:
    resolved = resolve_country(country)
    if resolved is None:
        return None
    for language in resolved.languages:
        normalized = str(language or "").strip().lower()
        if normalized and normalized != "en":
            return normalized
    return None


def country_search_languages(country: str | None, languages: list[str]) -> tuple[str, ...]:
    normalized_languages = [
        str(language or "").strip().lower()
        for language in languages
        if str(language or "").strip()
    ]
    seen: set[str] = set()
    ordered: list[str] = []

    def add(language: str | None) -> None:
        normalized = str(language or "").strip().lower()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        ordered.append(normalized)

    # English is always the primary search language.
    add("en")
    resolved = resolve_country(country)
    if resolved is None:
        for language in normalized_languages:
            add(language)
        return tuple(ordered)

    official_languages = {
        str(language or "").strip().lower()
        for language in resolved.languages
        if str(language or "").strip()
    }
    for language in normalized_languages:
        if language != "en" and language in official_languages:
            add(language)
    return tuple(ordered)


def next_refresh_at(reference: datetime | None = None) -> datetime:
    base = reference or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base + timedelta(days=REFRESH_INTERVAL_DAYS)


def keyword_variants(keyword: str) -> tuple[str, ...]:
    base = " ".join(str(keyword or "").split()).strip()
    if not base:
        return ()
    lowered = normalize_keyword(base)
    variants: list[str] = []
    seen: set[str] = set()

    def add(value: str | None) -> None:
        candidate = " ".join(str(value or "").split()).strip()
        normalized = normalize_keyword(candidate)
        if not candidate or not normalized or normalized in seen:
            return
        seen.add(normalized)
        variants.append(candidate)

    add(base)
    if lowered == "laser land level":
        add("laser land leveler")
        add("laser land leveller")
        add("gps land leveler")
        add("land leveler")
    elif lowered == "laser land leveler":
        add("laser land leveller")
        add("gps land leveler")
        add("land leveler")
    elif lowered == "laser land leveller":
        add("laser land leveler")
        add("gps land leveler")
        add("land leveler")
    elif lowered == "rtk land level":
        add("rtk land leveler")
        add("gps land leveler")
        add("land leveler")
    elif lowered == "rtk land leveler":
        add("gps land leveler")
        add("land leveler")
    elif lowered == "land level":
        add("land leveler")
        add("land leveller")
    return tuple(variants)


def build_keyword_queries(
    keyword: str,
    *,
    countries: list[str],
    languages: list[str],
    stage: int,
) -> list[dict[str, str | int]]:
    templates = PRIMARY_QUERY_TEMPLATES if stage == 1 else SECONDARY_QUERY_TEMPLATES
    variants = keyword_variants(keyword) if stage == 1 else (keyword,)
    query_items: list[dict[str, str | int]] = []
    target_countries = countries or [""]
    country_language_pairs: list[tuple[str, str, str, str]] = []
    for country in target_countries:
        for language in country_search_languages(country, languages):
            country_term = preferred_country_search_term(country, language) or str(country or "").strip()
            country_language_pairs.append((country, language, country_term, country_gl(country)))
    for variant_index, keyword_variant in enumerate(variants):
        for template_index, template in enumerate(templates):
            for country, language, country_term, gl in country_language_pairs:
                    if country_term:
                        query = template.format(keyword=keyword_variant, country=country_term).strip()
                    else:
                        query = template.replace(" in {country}", "").format(keyword=keyword_variant, country="").strip()
                    query_items.append(
                        {
                            "query": query,
                            "query_key": f"s{stage}:{variant_index}:{template_index}:{gl}:{language}:{country_term.lower()}",
                            "country": country,
                            "gl": gl,
                            "language": language,
                            "stage": stage,
                        }
                    )
    return query_items
