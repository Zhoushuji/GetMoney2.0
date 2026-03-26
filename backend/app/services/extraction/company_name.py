import asyncio
import json
import random
import re
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

LEGAL_SUFFIXES_RAW = [
    r"S\.L\.", r"S\.A\.", r"S\.L\.U\.", r"S\.A\.U\.", r"S\.C\.", r"S\.R\.L\.",
    r"S\.r\.l\.", r"S\.p\.A\.", r"S\.n\.c\.", r"S\.a\.s\.", r"GmbH", r"AG", r"KG", r"OHG",
    r"GmbH\s*&\s*Co\.\s*KG", r"e\.K\.", r"Ltd\.?", r"Limited", r"Pty\.?\s*Ltd\.?", r"PLC",
    r"LLC", r"Inc\.?", r"Corp\.?", r"L\.P\.", r"LLP", r"B\.V\.", r"N\.V\.", r"V\.O\.F\.",
    r"Sp\.\s*z\s*o\.o\.", r"s\.r\.o\.", r"a\.s\.", r"S\.A\.S\.", r"S\.A\.R\.L\.", r"E\.U\.R\.L\.",
    r"ООО", r"ЗАО", r"ОАО", r"Pvt\.?\s*Ltd\.?", r"Co\.,?\s*Inc\.?", r"Mfg\.\s*Co\.,?\s*Inc\.?"]

LEGAL_SUFFIX_PATTERN = "|".join(sorted(LEGAL_SUFFIXES_RAW, key=len, reverse=True))
LEGAL_ENTITY_PATTERN = re.compile(r"([A-Z][A-Za-z0-9\s&\-\.,']{2,60}?)\s+(" + LEGAL_SUFFIX_PATTERN + r")\b", re.UNICODE)
LEGAL_ENTITY_UPPER_PATTERN = re.compile(r"([A-Z][A-Z0-9\s&\-,\'\.]{4,60}?)\s+(" + LEGAL_SUFFIX_PATTERN + r")\b")

PRODUCT_NAME_INDICATORS = [
    r"\b(laser|level|leveler|leveller|sensor|meter|scale|scales|tool|device|machine|scanner|instrument|instruments|thermometer|detector|gauge|receiver)\b",
    r"\b(rotating|rotary|digital|manual|optical|automatic|electronic)\b",
    r"\b(NL|RL|GL|DL|SL|LL)\s*\d+", r"\d{3,}[A-Z]{1,3}", r"\b(series|model|type|version|edition)\b", r"^\d",
]

INVALID_NAME_PATTERNS = [
    r"^Name$", r"^Smart\s+Shopping", r"^Home$", r"^Welcome", r"^Index$", r"^Default$", r"^Untitled", r"^\s*$",
    r"^(Error|404|403|500)", r"^(Page|Site|Web)", r"^[\W\d]+$",
]

GENERIC_PAGE_LABEL_PATTERNS = [
    r"about(?:\s+us)?",
    r"our\s+company",
    r"company",
    r"unternehmen",
    r"ueber\s+uns",
    r"geschichte",
    r"history",
    r"kontakt",
    r"contact",
    r"imprint",
    r"privacy(?:\s+policy)?",
    r"legal(?:\s+notice)?",
    r"home",
    r"start",
    r"news",
    r"references?",
    r"quality(?:\s+management)?",
    r"products?",
    r"services?",
    r"applications?",
]
GENERIC_PAGE_LABEL_PATTERN = re.compile(
    r"^(?:" + "|".join(GENERIC_PAGE_LABEL_PATTERNS) + r")(?:\b|$)",
    re.I,
)

ABOUT_PATHS = [
    "/company", "/about-us", "/about", "/about_us", "/ueber-uns", "/uber-uns", "/unternehmen", "/firma",
    "/o-nas", "/o-firmie", "/o-spolecnosti", "/qui-sommes-nous", "/a-propos", "/chi-siamo", "/azienda",
    "/sobre-nosotros", "/empresa", "/quienes-somos", "/over-ons", "/sobre-nos",
]
LANG_PREFIXES = ["/en", "/es", "/de", "/fr", "/it", "/pt", "/nl", "/pl", "/cs", "/ru"]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


class CompanyNameExtractor:
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        self._client = http_client
        self._own_client = http_client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={"User-Agent": _random_ua()})
        return self._client

    async def close(self):
        if self._own_client and self._client:
            await self._client.aclose()

    def _looks_like_generic_page_label(self, text: str) -> bool:
        normalized = re.sub(r"\s+", " ", (text or "").strip())
        return bool(normalized and GENERIC_PAGE_LABEL_PATTERN.match(normalized))

    def _compact(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (value or "").lower())

    def _matches_site_brand(self, candidate: str, url: str) -> bool:
        compact_candidate = self._compact(candidate)
        compact_domain = self._compact(self._from_domain(url))
        if not compact_candidate or not compact_domain:
            return True
        return compact_domain in compact_candidate or compact_candidate in compact_domain

    def _is_valid_name(self, name: str) -> bool:
        if not name or not name.strip():
            return False
        name = name.strip()
        if len(name) < 2 or len(name) > 120:
            return False
        if self._looks_like_generic_page_label(name):
            return False
        return not any(re.search(p, name, re.I) for p in INVALID_NAME_PATTERNS)

    def _is_product_name(self, text: str) -> bool:
        normalized = re.sub(r"\s+", " ", (text or "")).strip()
        if not normalized:
            return False

        hits = sum(1 for pattern in PRODUCT_NAME_INDICATORS if re.search(pattern, normalized, re.I))
        if hits >= 2:
            return True
        return hits >= 1 and bool(re.search(r"\b\d{2,}\b|\b\d+[A-Z]+\b", normalized, re.I))

    def _clean_name(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        raw = raw.strip()
        candidates = [raw]
        for sep in [" | ", " - ", " – ", " — ", " · ", " :: ", " » ", " > ", ": "]:
            if sep in raw:
                candidates = [part.strip() for part in raw.split(sep) if part.strip()]
                break

        for candidate in candidates:
            candidate = re.sub(
                r"^(Get|Buy|Find|Best|Top|Cheap|Quality|Wholesale|Official|Welcome\s+to)\s+",
                "",
                candidate,
                flags=re.I,
            ).strip()
            if self._is_valid_name(candidate):
                return candidate
        return None

    def _from_jsonld(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        candidates: list[str] = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
                for item in items:
                    item_type = item.get("@type", "")
                    if any(x in str(item_type) for x in ("Organization", "LocalBusiness", "Corporation")):
                        legal = item.get("legalName", "")
                        if legal and self._is_valid_name(legal):
                            return self._clean_name(legal) or legal
                        name = item.get("name", "")
                        if name and self._is_valid_name(name):
                            candidates.append(name)
                    elif "WebSite" in str(item_type):
                        name = item.get("name", "")
                        if name:
                            candidates.append(name)
            except Exception:
                continue
        for c in candidates:
            cleaned = self._clean_name(c)
            if cleaned:
                return cleaned
        return None

    def _from_microdata(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        for item in soup.find_all(attrs={"itemtype": re.compile(r"schema\.org/(Organization|Corporation|LocalBusiness)")}):
            el = item.find(attrs={"itemprop": "name"})
            if el:
                cleaned = self._clean_name(el.get_text(strip=True) or el.get("content", ""))
                if cleaned:
                    return cleaned
        for item in soup.find_all(attrs={"typeof": re.compile(r"schema:Organization|org:Organization")}):
            el = item.find(attrs={"property": re.compile(r"schema:name|org:name")})
            if el:
                cleaned = self._clean_name(el.get_text(strip=True))
                if cleaned:
                    return cleaned
        return None

    def _from_og_site_name(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        for meta in [soup.find("meta", property="og:site_name"), soup.find("meta", attrs={"name": "application-name"})]:
            if meta and meta.get("content"):
                cleaned = self._clean_name(meta["content"])
                if cleaned:
                    return cleaned
        return None

    async def _from_about_pages(self, base_url: str) -> Optional[str]:
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        lang_prefix = next((p for p in LANG_PREFIXES if parsed.path.startswith(p + "/")), "")
        paths = ([lang_prefix + p for p in ABOUT_PATHS] if lang_prefix else []) + ABOUT_PATHS
        if not lang_prefix:
            for prefix in LANG_PREFIXES[:4]:
                paths += [prefix + p for p in ABOUT_PATHS[:4]]

        client = await self._get_client()
        deadline = asyncio.get_event_loop().time() + 25
        for path in paths:
            if asyncio.get_event_loop().time() > deadline:
                break
            try:
                resp = await asyncio.wait_for(client.get(base + path, headers={"User-Agent": _random_ua()}), timeout=5)
                if resp.status_code != 200 or len(resp.text) < 200:
                    continue
                html = resp.text
                name = (
                    self._from_jsonld(html)
                    or self._from_og_site_name(html)
                    or self._from_legal_entity_pattern(html)
                    or self._h1_safe(html)
                    or self._h2_safe(html)
                )
                if name:
                    return name
            except Exception:
                continue
        return None

    def _h1_safe(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.find("h1")
        if not h1:
            return None
        text = h1.get_text(strip=True)
        if self._is_product_name(text):
            return None
        return self._clean_name(text)

    def _h2_safe(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        for h2 in soup.find_all("h2")[:3]:
            text = h2.get_text(strip=True)
            if not self._is_product_name(text):
                cleaned = self._clean_name(text)
                if cleaned:
                    return cleaned
        return None

    def _normalize_legal_entity_candidate(self, base: str, suffix: str) -> Optional[str]:
        merged = re.sub(r"\s+", " ", f"{base.strip()} {suffix}".strip())
        tail_pattern = re.compile(
            rf"([A-Z0-9][A-Za-z0-9&\-',\.]*(?:\s+[A-Z0-9][A-Za-z0-9&\-',\.]*){{0,6}})\s+{re.escape(suffix)}\b"
        )

        for tail in reversed(tail_pattern.findall(merged)):
            candidate = re.sub(r"^(?:the|and)\s+", "", f"{tail.strip()} {suffix}".strip(), flags=re.I)
            cleaned = self._clean_name(candidate)
            if cleaned and not self._is_product_name(cleaned):
                return cleaned

        cleaned = self._clean_name(merged)
        if cleaned and not self._is_product_name(cleaned):
            return cleaned
        return None

    def _from_legal_entity_pattern(self, html: str) -> Optional[str]:
        text = BeautifulSoup(html, "html.parser").get_text(separator=" ")[:5000]
        for base, suffix in LEGAL_ENTITY_UPPER_PATTERN.findall(text):
            candidate = self._normalize_legal_entity_candidate(base, suffix)
            if candidate:
                return candidate
        for base, suffix in LEGAL_ENTITY_PATTERN.findall(text):
            candidate = self._normalize_legal_entity_candidate(base, suffix)
            if candidate:
                return candidate
        return None

    def _from_serper(self, serper_result: dict) -> Optional[str]:
        kg = serper_result.get("knowledgeGraph", {})
        if kg.get("title"):
            cleaned = self._clean_name(kg["title"])
            if cleaned:
                return cleaned
        for sl in serper_result.get("sitelinks", [])[:1]:
            if sl.get("title"):
                cleaned = self._clean_name(sl["title"])
                if cleaned:
                    return cleaned
        return None

    def _from_title(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        if not soup.title:
            return None
        raw = soup.title.string or ""
        if self._is_product_name(raw):
            return None
        return self._clean_name(raw)

    def _from_domain(self, url: str) -> str:
        domain = urlparse(url).netloc.replace("www.", "")
        return domain.split(".")[0].replace("-", " ").replace("_", " ").title()

    async def extract(self, url: str, serper_result: Optional[dict] = None, homepage_html: Optional[str] = None) -> str:
        serper_result = serper_result or {}
        title_name = None
        if homepage_html:
            for extractor in (self._from_jsonld, self._from_microdata, self._from_og_site_name):
                name = extractor(homepage_html)
                if name:
                    return name
            title_name = self._from_title(homepage_html)

        about_task = asyncio.create_task(self._from_about_pages(url))
        name_serper = self._from_serper(serper_result)
        try:
            name_about = await asyncio.wait_for(about_task, timeout=26)
        except asyncio.TimeoutError:
            name_about = None

        if title_name:
            return title_name
        if name_serper and self._matches_site_brand(name_serper, url):
            return name_serper
        if name_about and self._matches_site_brand(name_about, url):
            return name_about
        return self._from_domain(url)
