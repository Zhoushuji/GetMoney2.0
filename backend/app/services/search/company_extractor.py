import asyncio
import re
from dataclasses import dataclass
from typing import Awaitable, Callable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

PRICE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:Lakh|lakh|USD|INR|Rs\.?|₹|\$)\b", re.I)
DESCRIPTIVE_PREFIX_PATTERN = re.compile(r"^(Get|Buy|Find|Best|Top|Cheap|Quality)\s+", re.I)
INVALID_PATTERN = re.compile(r"^[\W\d_]+$")


@dataclass
class ExtractedCompanyName:
    value: str
    source: str


class CompanyNameExtractor:
    ABOUT_PATHS = [
        "/about", "/about-us", "/about_us", "/company",
        "/o-nas", "/o-firmie", "/uber-uns", "/ueber-uns",
        "/qui-sommes-nous", "/chi-siamo", "/sobre-nosotros", "/o-kompanii",
    ]

    async def extract(self, serper_item: dict, website: str, homepage_soup: BeautifulSoup | None, fetch_page: Callable[[str, float], Awaitable[BeautifulSoup | None]] | None = None) -> ExtractedCompanyName:
        candidates: list[tuple[str | None, str]] = [
            (self._extract_knowledge_graph_name(serper_item), "knowledge_graph"),
            (self._extract_sitelink_name(serper_item), "sitelinks"),
        ]

        if homepage_soup is not None:
            candidates.extend([
                (self._extract_meta(homepage_soup, "property", "og:site_name"), "og:site_name"),
                (self._extract_meta(homepage_soup, "name", "application-name"), "application_name"),
                (self._extract_title(homepage_soup), "title"),
            ])

        if fetch_page is not None:
            about_name = await self._extract_from_about_pages(website, fetch_page)
            if about_name:
                candidates.append(about_name)

        if homepage_soup is not None:
            candidates.append((self._extract_h1(homepage_soup), "h1"))

        candidates.extend([
            (serper_item.get("title"), "search_title"),
            (serper_item.get("snippet"), "snippet"),
        ])

        for raw, source in candidates:
            cleaned = self.clean_title(raw or "")
            if self._is_valid(cleaned):
                return ExtractedCompanyName(value=cleaned, source=source)

        return ExtractedCompanyName(value=self._domain_brand(website), source="domain_fallback")

    async def _extract_from_about_pages(self, website: str, fetch_page: Callable[[str, float], Awaitable[BeautifulSoup | None]]) -> tuple[str | None, str] | None:
        for path in self.ABOUT_PATHS:
            url = urljoin(website, path)
            try:
                soup = await asyncio.wait_for(fetch_page(url, timeout=5.0), timeout=5.0)
            except Exception:
                continue
            if soup is None:
                continue
            for extractor, source in [
                (lambda s: self._extract_meta(s, "property", "og:site_name"), "about_og:site_name"),
                (self._extract_h1, "about_h1"),
                (self._extract_title, "about_title"),
            ]:
                value = extractor(soup)
                if value:
                    return value, source
        return None

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
        return bool(candidate and len(candidate) >= 3 and not INVALID_PATTERN.fullmatch(candidate))

    def _domain_brand(self, website: str) -> str:
        host = urlparse(website).netloc.removeprefix("www.")
        label = host.split(".")[0]
        label = re.sub(r"[-_]+", " ", label)
        return re.sub(r"\s+", " ", label).strip().title() or "Unknown"
