from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import phonenumbers
from bs4 import BeautifulSoup

_RAW_GEO_DATA_PATTERN = re.compile(
    r'const rawGeoData: Array<Omit<GeoEntry, "name_zh">> = (\[[\s\S]*?\n\]);'
)
_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_DETAIL_LINK_HINTS = (
    "contact",
    "about",
    "company",
    "office",
    "location",
    "imprint",
    "impressum",
    "kontakt",
    "contato",
    "contacto",
    "entreprise",
    "empresa",
    "firma",
    "unternehmen",
)
_DETAIL_FALLBACK_PATHS = (
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/company",
    "/imprint",
    "/impressum",
    "/kontakt",
    "/empresa",
    "/unternehmen",
)
_CONTACT_CONTEXT_HINTS = (
    "address",
    "location",
    "office",
    "head office",
    "headquarters",
    "factory",
    "warehouse",
    "contact",
    "kontakt",
    "find us",
    "phone",
    "tel",
    "whatsapp",
    "fax",
    "mobile",
    "mob",
)
_CUSTOM_ALIASES: dict[str, tuple[str, ...]] = {
    "AE": ("UAE", "Emirates", "United Arab Emirates"),
    "GB": ("UK", "Britain", "Great Britain", "United Kingdom"),
    "US": ("USA", "US", "United States", "United States of America"),
    "CZ": ("Czech Republic",),
    "KR": ("South Korea", "Republic of Korea"),
    "KP": ("North Korea", "DPRK"),
    "RU": ("Russian Federation",),
    "IR": ("Iran", "Islamic Republic of Iran"),
    "SY": ("Syria", "Syrian Arab Republic"),
    "LA": ("Laos", "Lao PDR", "Lao People's Democratic Republic"),
    "MD": ("Moldova", "Republic of Moldova"),
    "BO": ("Bolivia", "Plurinational State of Bolivia"),
    "VE": ("Venezuela", "Bolivarian Republic of Venezuela"),
    "CI": ("Ivory Coast", "Cote d'Ivoire"),
    "CD": ("DR Congo", "Democratic Republic of the Congo", "Congo-Kinshasa"),
    "CG": ("Republic of the Congo", "Congo-Brazzaville"),
    "TZ": ("Tanzania", "United Republic of Tanzania"),
    "CV": ("Cape Verde",),
    "PS": ("Palestine", "State of Palestine"),
    "MM": ("Myanmar", "Burma"),
    "TW": ("Taiwan", "Taiwan, Province of China"),
}
_CC_TLD_OVERRIDES: dict[str, tuple[str, ...]] = {
    "GB": (".uk", ".gb"),
}


def _ascii_fold(value: Any) -> str:
    text = "" if value is None else str(value)
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _normalize_ascii_token(value: Any) -> str:
    ascii_value = _ascii_fold(value).lower()
    collapsed = _NON_ALNUM_RE.sub(" ", ascii_value)
    return _WHITESPACE_RE.sub(" ", collapsed).strip()


def _normalize_raw_token(value: Any) -> str:
    text = "" if value is None else str(value)
    return _WHITESPACE_RE.sub(" ", text.lower()).strip()


def _unique(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)


@dataclass(frozen=True)
class CountryMetadata:
    code: str
    name_en: str
    name_local: str
    continent: str
    languages: tuple[str, ...]
    lookup_keys: tuple[str, ...]
    ascii_text_aliases: tuple[str, ...]
    raw_text_aliases: tuple[str, ...]
    cc_tlds: tuple[str, ...]
    phone_country_code: int | None

    @property
    def gl(self) -> str:
        return self.code.lower()

    def preferred_search_term(self, language: str | None) -> str:
        if not language or language == "en":
            return self.name_en
        if language in self.languages:
            local_ascii = _normalize_ascii_token(self.name_local)
            english_ascii = _normalize_ascii_token(self.name_en)
            if self.name_local and (_normalize_raw_token(self.name_local) != _normalize_raw_token(self.name_en)) and (not local_ascii or local_ascii != english_ascii):
                return self.name_local
        return self.name_en


@dataclass(frozen=True)
class CountryDetectionResult:
    target_country_code: str | None
    target_country_name: str | None
    detected_country_code: str | None
    detected_country_name: str | None
    continent: str | None
    confidence: float
    evidence: tuple[dict[str, Any], ...]
    mismatch_reason: str | None

    @property
    def status(self) -> str:
        if self.detected_country_code is None:
            return "unknown"
        if self.target_country_code and self.detected_country_code != self.target_country_code:
            return "mismatch"
        return "matched"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "target_country_code": self.target_country_code,
            "target_country_name": self.target_country_name,
            "detected_country_code": self.detected_country_code,
            "detected_country_name": self.detected_country_name,
            "continent": self.continent,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "mismatch_reason": self.mismatch_reason,
        }


class CountryCatalog:
    def __init__(self, countries: tuple[CountryMetadata, ...]) -> None:
        self._countries = countries
        self._by_code = {country.code: country for country in countries}
        self._lookup: dict[str, CountryMetadata] = {}
        for country in countries:
            for key in country.lookup_keys:
                self._lookup[key] = country

    def resolve(self, value: str | None) -> CountryMetadata | None:
        if not value:
            return None
        for key in (_normalize_raw_token(value), _normalize_ascii_token(value), value.upper().strip()):
            if not key:
                continue
            country = self._lookup.get(key)
            if country is not None:
                return country
        return None

    def by_code(self, code: str | None) -> CountryMetadata | None:
        if not code:
            return None
        return self._by_code.get(code.upper())

    def detect_cc_tld(self, host: str | None) -> tuple[CountryMetadata | None, str | None]:
        hostname = (host or "").lower().strip()
        if not hostname:
            return None, None
        for country in self._countries:
            for suffix in country.cc_tlds:
                if hostname.endswith(suffix):
                    return country, suffix
        return None, None

    def match_text(self, text: str | None) -> dict[str, str]:
        raw_text = _normalize_raw_token(text or "")
        ascii_text = f" {_normalize_ascii_token(text or '')} "
        matches: dict[str, str] = {}
        for country in self._countries:
            for alias in country.ascii_text_aliases:
                if f" {alias} " in ascii_text:
                    matches[country.code] = alias
                    break
            if country.code in matches:
                continue
            for alias in country.raw_text_aliases:
                if alias and alias in raw_text:
                    matches[country.code] = alias
                    break
        return matches


def _frontend_geo_path() -> Path:
    return Path(__file__).resolve().parents[4] / "frontend" / "src" / "data" / "geo.ts"


def _build_lookup_keys(code: str, aliases: tuple[str, ...]) -> tuple[str, ...]:
    keys = [code.upper()]
    for alias in aliases:
        raw = _normalize_raw_token(alias)
        if raw:
            keys.append(raw)
        ascii_key = _normalize_ascii_token(alias)
        if ascii_key:
            keys.append(ascii_key)
    return _unique(keys)


def _build_text_aliases(code: str, aliases: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    ascii_aliases: list[str] = []
    raw_aliases: list[str] = []
    for alias in aliases:
        normalized_ascii = _normalize_ascii_token(alias)
        normalized_raw = _normalize_raw_token(alias)
        if normalized_ascii and (len(normalized_ascii) >= 4 or normalized_ascii in {"uae", "usa"}):
            ascii_aliases.append(normalized_ascii)
        if normalized_raw and normalized_raw != normalized_ascii:
            raw_aliases.append(normalized_raw)
    return _unique(ascii_aliases), _unique(raw_aliases)


def _build_cc_tlds(code: str) -> tuple[str, ...]:
    defaults = [f".{code.lower()}"]
    overrides = list(_CC_TLD_OVERRIDES.get(code.upper(), ()))
    return _unique(overrides + defaults)


@lru_cache(maxsize=1)
def get_country_catalog() -> CountryCatalog:
    text = _frontend_geo_path().read_text(encoding="utf-8")
    match = _RAW_GEO_DATA_PATTERN.search(text)
    if match is None:
        raise RuntimeError("Could not load frontend geo data.")
    raw_entries = json.loads(match.group(1))
    countries: list[CountryMetadata] = []
    for entry in raw_entries:
        code = str(entry["code"]).upper()
        name_en = str(entry["name_en"]).strip()
        name_local = str(entry["name_local"]).strip() or name_en
        aliases = _unique([name_en, name_local, *_CUSTOM_ALIASES.get(code, ())])
        lookup_keys = _build_lookup_keys(code, aliases)
        ascii_text_aliases, raw_text_aliases = _build_text_aliases(code, aliases)
        try:
            phone_country_code = int(phonenumbers.country_code_for_region(code))
        except Exception:
            phone_country_code = None
        countries.append(
            CountryMetadata(
                code=code,
                name_en=name_en,
                name_local=name_local,
                continent=str(entry["continent"]).strip(),
                languages=tuple(entry.get("languages") or []),
                lookup_keys=lookup_keys,
                ascii_text_aliases=ascii_text_aliases,
                raw_text_aliases=raw_text_aliases,
                cc_tlds=_build_cc_tlds(code),
                phone_country_code=phone_country_code or None,
            )
        )
    countries.sort(key=lambda item: item.code)
    return CountryCatalog(tuple(countries))


def resolve_country(value: str | None) -> CountryMetadata | None:
    return get_country_catalog().resolve(value)


def country_gl(value: str | None, fallback: str = "us") -> str:
    country = resolve_country(value)
    return country.gl if country is not None else fallback


def preferred_country_search_term(value: str | None, language: str | None) -> str:
    country = resolve_country(value)
    if country is None:
        return (value or "").strip()
    return country.preferred_search_term(language)


class CountryDetector:
    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client
        self._catalog = get_country_catalog()

    async def detect(
        self,
        *,
        website: str,
        target_country: str | None,
        search_title: str | None = None,
        search_snippet: str | None = None,
        homepage_html: str | None = None,
    ) -> CountryDetectionResult:
        target = self._catalog.resolve(target_country)
        scores: dict[str, int] = defaultdict(int)
        evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)

        def add(country: CountryMetadata, weight: int, signal: str, value: str) -> None:
            if weight <= 0 or not value:
                return
            scores[country.code] += weight
            evidence[country.code].append({
                "country_code": country.code,
                "country_name": country.name_en,
                "signal": signal,
                "value": value,
                "weight": weight,
            })

        parsed = urlparse(website)
        host = parsed.netloc.lower()
        tld_country, suffix = self._catalog.detect_cc_tld(host)
        if tld_country is not None and suffix is not None:
            add(tld_country, 4, "cc_tld", suffix)

        for signal, value in (("search_title", search_title), ("search_snippet", search_snippet)):
            for code, alias in self._catalog.match_text(value).items():
                country = self._catalog.by_code(code)
                if country is not None:
                    add(country, 1, signal, alias)

        pages: list[tuple[str, str]] = []
        if homepage_html:
            pages.append(("homepage", homepage_html))
            for page in await self._fetch_supporting_pages(website, homepage_html):
                pages.append(page)

        for label, html in pages:
            for country in self._extract_structured_countries(html):
                add(country, 6, f"{label}_structured", country.name_en)

            for fragment in self._extract_text_fragments(html):
                matches = self._catalog.match_text(fragment)
                if not matches:
                    continue
                weight = 2 if self._is_contact_context(fragment) else 1
                for code, alias in matches.items():
                    country = self._catalog.by_code(code)
                    if country is not None:
                        add(country, weight, f"{label}_text", alias)

            for country, phone in self._extract_phone_countries(html):
                add(country, 4, f"{label}_phone", phone)

        top_country: CountryMetadata | None = None
        confidence = 0.0
        if scores:
            ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            top_country = self._catalog.by_code(ordered[0][0])
            top_score = ordered[0][1]
            runner_up = ordered[1][1] if len(ordered) > 1 else 0
            if top_score < 4 or (runner_up >= top_score - 1 and top_score < 6):
                top_country = None
            else:
                confidence = round(min(0.99, max(0.35, top_score / max(top_score + runner_up, 1))), 2)

        mismatch_reason: str | None = None
        if target is not None:
            if top_country is None:
                mismatch_reason = "Unable to verify the company country from website, phone, TLD, or structured data."
            elif top_country.code != target.code:
                mismatch_reason = f"Detected {top_country.name_en} instead of target market {target.name_en}."

        top_evidence = tuple(evidence.get(top_country.code, [])) if top_country is not None else ()
        return CountryDetectionResult(
            target_country_code=target.code if target is not None else None,
            target_country_name=target.name_en if target is not None else None,
            detected_country_code=top_country.code if top_country is not None else None,
            detected_country_name=top_country.name_en if top_country is not None else None,
            continent=top_country.continent if top_country is not None else None,
            confidence=confidence,
            evidence=top_evidence,
            mismatch_reason=mismatch_reason,
        )

    async def _fetch_supporting_pages(self, website: str, homepage_html: str) -> list[tuple[str, str]]:
        client = self._client
        if client is None:
            return []
        candidates = self._candidate_detail_urls(website, homepage_html)
        pages: list[tuple[str, str]] = []
        for url in candidates[:2]:
            html = await self._fetch_html(url)
            if html:
                pages.append((urlparse(url).path or "/", html))
        return pages

    async def _fetch_html(self, url: str) -> str | None:
        if self._client is None:
            return None
        try:
            response = await self._client.get(url, headers={"User-Agent": "Mozilla/5.0 LeadGenBot/1.0"})
            response.raise_for_status()
            return response.text
        except Exception:
            return None

    def _candidate_detail_urls(self, website: str, homepage_html: str) -> list[str]:
        base = urlparse(website)
        root = f"{base.scheme or 'https'}://{base.netloc}"
        urls: list[str] = []
        soup = BeautifulSoup(homepage_html, "html.parser")
        for node in soup.find_all("a", href=True):
            href = node.get("href", "")
            candidate = urljoin(root, href)
            parsed = urlparse(candidate)
            if parsed.netloc != base.netloc:
                continue
            path = parsed.path.lower()
            if any(hint in path for hint in _DETAIL_LINK_HINTS):
                urls.append(f"{root}{parsed.path}")
        urls.extend(f"{root}{path}" for path in _DETAIL_FALLBACK_PATHS)
        return list(dict.fromkeys(urls))

    def _extract_structured_countries(self, html: str) -> list[CountryMetadata]:
        countries: list[CountryMetadata] = []
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or script.get_text() or ""
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            for value in self._walk_country_values(data):
                country = self._catalog.resolve(value)
                if country is not None:
                    countries.append(country)
        return countries

    def _walk_country_values(self, payload: Any) -> list[str]:
        collected: list[str] = []
        if isinstance(payload, dict):
            for key, value in payload.items():
                lowered = str(key).lower()
                if lowered in {"addresscountry", "country"}:
                    if isinstance(value, str):
                        collected.append(value)
                    elif isinstance(value, dict):
                        collected.extend(self._walk_country_values(value))
                elif lowered in {"areaserved", "location", "foundinglocation"}:
                    if isinstance(value, str):
                        collected.append(value)
                    elif isinstance(value, dict):
                        if isinstance(value.get("name"), str):
                            collected.append(value["name"])
                        collected.extend(self._walk_country_values(value))
                    elif isinstance(value, list):
                        for item in value:
                            collected.extend(self._walk_country_values(item))
                else:
                    collected.extend(self._walk_country_values(value))
        elif isinstance(payload, list):
            for item in payload:
                collected.extend(self._walk_country_values(item))
        return collected

    def _extract_text_fragments(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        fragments: list[str] = []
        if soup.title and soup.title.string:
            fragments.append(soup.title.string)
        for meta in soup.find_all("meta", attrs={"content": True}):
            content = meta.get("content")
            if content:
                fragments.append(content)
        for block in soup.get_text("\n").splitlines():
            compact = _WHITESPACE_RE.sub(" ", block).strip()
            if compact and len(compact) <= 220:
                fragments.append(compact)
        return list(dict.fromkeys(fragments[:160]))

    def _extract_phone_countries(self, html: str) -> list[tuple[CountryMetadata, str]]:
        text = BeautifulSoup(html, "html.parser").get_text(" ")
        matches: list[tuple[CountryMetadata, str]] = []
        for phone_match in phonenumbers.PhoneNumberMatcher(text, None):
            number = phone_match.number
            if not phonenumbers.is_valid_number(number):
                continue
            region = phonenumbers.region_code_for_number(number)
            country = self._catalog.by_code(region)
            if country is None:
                continue
            formatted = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            matches.append((country, formatted))
        deduped: dict[tuple[str, str], tuple[CountryMetadata, str]] = {}
        for country, phone in matches:
            deduped[(country.code, phone)] = (country, phone)
        return list(deduped.values())

    def _is_contact_context(self, fragment: str) -> bool:
        normalized = _normalize_ascii_token(fragment)
        return any(hint in normalized for hint in _CONTACT_CONTEXT_HINTS) or bool(re.search(r"\+\d", fragment))
