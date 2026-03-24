import asyncio
import re
from dataclasses import dataclass
from typing import Awaitable, Callable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

PRICE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:Lakh|lakh|USD|INR|Rs\.?|₹|\$)\b", re.I)
DESCRIPTIVE_PREFIX_PATTERN = re.compile(r"^(Get|Buy|Find|Best|Top|Cheap|Quality)\s+", re.I)
INVALID_PATTERN = re.compile(r"^[\W\d_]+$")
PLACEHOLDER_PATTERNS = [
    re.compile(r"future home of", re.I),
    re.compile(r"coming soon", re.I),
    re.compile(r"under construction", re.I),
]
GENERIC_MARKETPLACE_PATTERN = re.compile(r"\b(manufacturer|manufacturers|supplier|suppliers|exporter|exporters|price|product|products)\b", re.I)


@dataclass
class ExtractedCompanyName:
    value: str
    source: str


class CompanyNameExtractor:
    ABOUT_PATHS = [
        "/company", "/about", "/about-us", "/about_us", "/ueber-uns", "/uber-uns", "/unternehmen",
        "/o-nas", "/o-firmie", "/qui-sommes-nous", "/chi-siamo", "/sobre-nosotros",
    ]
    LEGAL_SUFFIXES = [
        "GmbH", "AG", "KG", "OHG", "GmbH & Co. KG",
        "Ltd", "Limited", "LLC", "Inc", "Corp",
        "S.A.", "S.L.", "S.r.l.", "S.p.A.",
        "B.V.", "N.V.",
        "Sp. z o.o.",
        "Pty Ltd", "Pty. Ltd.",
        "Pvt Ltd", "Pvt. Ltd.",
    ]

    async def extract(
        self,
        serper_item: dict,
        website: str,
        homepage_soup: BeautifulSoup | None,
        fetch_page: Callable[[str, float], Awaitable[BeautifulSoup | None]] | None = None,
    ) -> ExtractedCompanyName:
        candidates: list[tuple[str | None, str]] = [
            (self._extract_knowledge_graph_name(serper_item), "knowledge_graph"),
            (self._extract_sitelink_name(serper_item), "sitelinks"),
        ]

        about_text = ""
        if fetch_page is not None:
            about_text, about_name = await self._extract_from_about_pages(website, fetch_page)
            if about_name:
                candidates.append((about_name, "about_page"))

        if homepage_soup is not None:
            homepage_meta = self._extract_meta(homepage_soup, "property", "og:site_name")
            homepage_app = self._extract_meta(homepage_soup, "name", "application-name")
            homepage_title = self._extract_title(homepage_soup)
            homepage_h1 = self._extract_h1(homepage_soup)
            if homepage_title and about_text:
                homepage_title = self.try_append_legal_suffix(homepage_title, about_text)

            candidates.extend([
                (homepage_meta, "og:site_name"),
                (homepage_app, "application_name"),
                (homepage_title, "title"),
                (homepage_h1, "h1"),
            ])

        candidates.extend([
            (serper_item.get("title"), "search_title"),
            (serper_item.get("snippet"), "snippet"),
        ])

        for raw, source in candidates:
            cleaned = self.clean_title(raw or "")
            if cleaned and source in {"title", "search_title", "snippet"}:
                cleaned = self._prefer_domain_brand_when_title_is_generic(cleaned, raw or "", website)
            if self._is_valid(cleaned):
                return ExtractedCompanyName(value=cleaned, source=source)

        return ExtractedCompanyName(value=self._domain_brand(website), source="domain_fallback")

    async def _extract_from_about_pages(
        self,
        website: str,
        fetch_page: Callable[[str, float], Awaitable[BeautifulSoup | None]],
    ) -> tuple[str, str | None]:
        aggregated_text: list[str] = []
        parsed = urlparse(website)
        lang_prefix = self._detect_lang_prefix(parsed.path)
        paths_to_try = list(self.ABOUT_PATHS)
        if lang_prefix:
            prefixed = [f"{lang_prefix}{p}" for p in self.ABOUT_PATHS if not p.startswith(lang_prefix)]
            paths_to_try = prefixed + paths_to_try

        start = asyncio.get_event_loop().time()
        for path in paths_to_try:
            if asyncio.get_event_loop().time() - start > 20:
                break
            url = urljoin(website, path)
            try:
                soup = await asyncio.wait_for(fetch_page(url, timeout=5.0), timeout=5.0)
            except Exception:
                continue
            if soup is None:
                continue
            aggregated_text.append(soup.get_text(" ", strip=True))
            for extractor in (
                lambda s: self._extract_meta(s, "property", "og:site_name"),
                self._extract_h1,
                self._extract_title,
            ):
                value = extractor(soup)
                if value:
                    return " ".join(aggregated_text), value
        return " ".join(aggregated_text), None

    def try_append_legal_suffix(self, name_from_step6: str, about_page_text: str) -> str:
        for suffix in self.LEGAL_SUFFIXES:
            pattern = rf"\b{re.escape(name_from_step6)}\s+{re.escape(suffix)}\b"
            if re.search(pattern, about_page_text, re.I):
                return f"{name_from_step6} {suffix}"
        return name_from_step6

    def clean_title(self, raw: str) -> str:
        candidate = re.sub(r"\s+", " ", raw or "").strip()
        if not candidate:
            return ""
        for sep in [";", "|", "·", " - ", " – ", ",", "-"]:
            if sep in candidate:
                candidate = candidate.split(sep, 1)[0].strip()
        candidate = PRICE_PATTERN.sub("", candidate)
        candidate = DESCRIPTIVE_PREFIX_PATTERN.sub("", candidate)
        candidate = re.sub(r"\s+", " ", candidate).strip(" -–|,;·")
        if len(candidate) > 80:
            return ""
        if candidate:
            candidate = candidate[0].upper() + candidate[1:]
        return candidate[:120].strip()

    def _extract_knowledge_graph_name(self, serper_item: dict) -> str | None:
        kg = serper_item.get("knowledgeGraph") or {}
        return kg.get("title") or kg.get("name")

    def _extract_sitelink_name(self, serper_item: dict) -> str | None:
        for key in ("sitelinks", "siteLinks"):
            sitelinks = serper_item.get(key) or []
            for link in sitelinks:
                if isinstance(link, dict) and link.get("title"):
                    return link["title"]
        return None

    def _extract_meta(self, soup: BeautifulSoup, attr: str, value: str) -> str | None:
        node = soup.find("meta", attrs={attr: value})
        return node.get("content") if node else None

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            for sep in ["|", "-"]:
                if sep in title:
                    return title.split(sep, 1)[0].strip()
            return title
        return None

    def _extract_h1(self, soup: BeautifulSoup) -> str | None:
        node = soup.find("h1") or soup.find("h2")
        return node.get_text(" ", strip=True) if node else None

    def _is_valid(self, candidate: str) -> bool:
        if not candidate or len(candidate) < 3 or INVALID_PATTERN.fullmatch(candidate):
            return False
        if any(pattern.search(candidate) for pattern in PLACEHOLDER_PATTERNS):
            return False
        return True

    def _detect_lang_prefix(self, path: str) -> str | None:
        match = re.match(r"^/(en|de|fr|pl|es|it)(?:/|$)", path or "", re.I)
        if match:
            return f"/{match.group(1).lower()}"
        return None

    def _domain_brand(self, website: str) -> str:
        host = urlparse(website).netloc.removeprefix("www.")
        label = host.split(".")[0]
        label = re.sub(r"[-_]+", " ", label)
        return re.sub(r"\s+", " ", label).strip().title() or "Unknown"

    def _prefer_domain_brand_when_title_is_generic(self, cleaned: str, raw: str, website: str) -> str:
        domain_brand = self._domain_brand(website)
        if not domain_brand:
            return cleaned
        if GENERIC_MARKETPLACE_PATTERN.search(cleaned) and domain_brand.lower() in (raw or "").lower():
            return domain_brand
        return cleaned
