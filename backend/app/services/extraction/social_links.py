import asyncio
import random
import re
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.services.search.social_links import _extract_urls_from_dom, extract_facebook, extract_linkedin_company
from app.services.search.serper import call_serper

FB_BLACKLIST = [
    r"facebook\.com/sharer", r"facebook\.com/share", r"facebook\.com/dialog/", r"facebook\.com/login", r"facebook\.com/plugins", r"facebook\.com/tr\?",
    r"\?u=", r"/watch/", r"/events/", r"/groups/", r"/marketplace/", r"/hashtag/", r"/pages/category/", r"facebook\.com/?$", r"facebook\.com/home",
]

FB_VALID = re.compile(r"https?://(?:www\.)?facebook\.com/(?!sharer|share|dialog|login|plugins|watch|events|groups|marketplace|hashtag|home|pages/category)([a-zA-Z0-9._-]{3,100})/?(?:\?.*)?$")
LI_VALID_COMPANY = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/([a-zA-Z0-9_\-]{2,100})/?(?:\?.*)?$")
LI_BLACKLIST = [r"linkedin\.com/in/", r"linkedin\.com/jobs/", r"linkedin\.com/posts/", r"linkedin\.com/pulse/", r"linkedin\.com/school/", r"linkedin\.com/showcase/"]
SCAN_PATHS = ["/", "/contact", "/contact-us", "/kontakt", "/kontakty", "/contacto", "/sobre-nosotros", "/about", "/about-us", "/imprint", "/impressum"]
LEGAL_SUFFIXES = {"gmbh", "ag", "kg", "ltd", "limited", "llc", "inc", "bv", "b.v", "srl", "s.a", "srl.", "corp", "co"}
GENERIC_TERMS = {"about", "about us", "contact", "home", "company", "unternehmen", "official"}
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


def _normalize_fb(url: str | None) -> Optional[str]:
    if not url or any(re.search(pattern, url, re.I) for pattern in FB_BLACKLIST):
        return None
    match = FB_VALID.search(url)
    if not match:
        return None
    return f"https://www.facebook.com/{match.group(1)}"


def _normalize_li_company(url: str | None) -> Optional[str]:
    if not url or any(re.search(pattern, url, re.I) for pattern in LI_BLACKLIST):
        return None
    match = LI_VALID_COMPANY.search(url)
    if not match:
        return None
    return f"https://www.linkedin.com/company/{match.group(1)}"


def _is_valid_fb(url: str) -> bool:
    return _normalize_fb(url) is not None


def _is_valid_li_company(url: str) -> bool:
    return _normalize_li_company(url) is not None


def _normalize_domain(domain: str) -> str:
    parsed = urlparse(domain if "://" in domain else f"https://{domain}")
    host = (parsed.netloc or parsed.path).strip().lower().removeprefix("www.")
    return host.rstrip("/")


def _candidate_base_urls(domain: str) -> list[str]:
    host = _normalize_domain(domain)
    if not host:
        return []
    candidates = [f"https://{host}"]
    if not host.startswith("www."):
        candidates.append(f"https://www.{host}")
    return candidates


def _is_useful_search_term(term: str) -> bool:
    normalized = re.sub(r"\s+", " ", (term or "").strip()).lower()
    if len(normalized) < 3 or normalized in GENERIC_TERMS:
        return False
    tokens = [token for token in re.split(r"[^a-z0-9]+", normalized) if token and token not in LEGAL_SUFFIXES]
    return bool(tokens)


def _build_search_terms(company_name: str, domain: str) -> list[str]:
    terms: list[str] = []

    def add(value: str | None):
        normalized = re.sub(r"\s+", " ", (value or "").strip())
        if not normalized or not _is_useful_search_term(normalized):
            return
        if normalized.lower() not in {term.lower() for term in terms}:
            terms.append(normalized)

    cleaned_company = re.sub(r"^https?://", "", (company_name or "").strip(), flags=re.I).removeprefix("www.")
    add(cleaned_company)
    stripped_company = " ".join(
        token for token in re.split(r"\s+", cleaned_company) if token.lower().strip(".,") not in LEGAL_SUFFIXES
    ).strip()
    add(stripped_company)

    host = _normalize_domain(domain)
    host_root = host.split(".", 1)[0]
    add(host_root.replace("-", " "))
    add(host_root)
    return terms


def _extract_from_html(html: str, base_url: str | None = None) -> tuple[Optional[str], Optional[str]]:
    if base_url:
        urls = _extract_urls_from_dom(html, base_url)
        normalized_text = "\n".join(sorted(urls))
        fb = extract_facebook(normalized_text)
        li = extract_linkedin_company(normalized_text)
        if fb or li:
            return fb, li

    urls: set[str] = set()
    urls.update(re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', html, re.I))
    urls.update(re.findall(r'data-(?:href|url|link)=["\']([^"\']+)["\']', html, re.I))
    urls.update(re.findall(r'(?:fb(?:Url|_url|Link|PageUrl)|facebook(?:Url|Link|Page))\s*[:=]\s*["\']([^"\']+)["\']', html, re.I))
    urls.update(re.findall(r'<meta[^>]+content=["\']([^"\']*(?:facebook|linkedin)[.]com[^"\']*)["\']', html, re.I))
    urls.update(re.findall(r'"sameAs"\s*:\s*\[?["\']([^"\']*(?:facebook|linkedin)[.]com[^"\']*)["\']', html))
    for block in re.findall(r'"sameAs"\s*:\s*\[([^\]]+)\]', html):
        for u in re.findall(r'"([^"]+)"', block):
            if "facebook.com" in u or "linkedin.com" in u:
                urls.add(u)

    fb = next((_normalize_fb(u) for u in urls if _normalize_fb(u)), None)
    li = next((_normalize_li_company(u) for u in urls if _normalize_li_company(u)), None)
    return fb, li


class SocialLinksExtractor:
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

    async def extract(self, company_name: str, domain: str) -> dict[str, Optional[str]]:
        track_a, track_b = await asyncio.gather(self._track_a(company_name, domain), self._track_b(domain), return_exceptions=True)
        if isinstance(track_a, Exception):
            track_a = {}
        if isinstance(track_b, Exception):
            track_b = {}
        return {"facebook": track_a.get("facebook") or track_b.get("facebook"), "linkedin": track_a.get("linkedin") or track_b.get("linkedin")}

    async def _track_a(self, company_name: str, domain: str) -> dict:
        fb_url = li_url = None
        search_terms = _build_search_terms(company_name, domain)
        try:
            for term in search_terms:
                for q in [f'"{term}" site:facebook.com -sharer -dialog -groups -events', f'site:facebook.com "{term}"']:
                    result = await call_serper(q, num=5)
                    for item in result.get("organic", []):
                        normalized = _normalize_fb(item.get("link", ""))
                        if normalized:
                            fb_url = normalized
                            break
                    if fb_url:
                        break
                if fb_url:
                    break
        except Exception:
            pass
        try:
            for term in search_terms:
                for q in [f'site:linkedin.com/company "{term}"', f'"{term}" linkedin company']:
                    result = await call_serper(q, num=5)
                    for item in result.get("organic", []):
                        normalized = _normalize_li_company(item.get("link", ""))
                        if normalized:
                            li_url = normalized
                            break
                    if li_url:
                        break
                if li_url:
                    break
        except Exception:
            pass
        return {"facebook": fb_url, "linkedin": li_url}

    async def _track_b(self, domain: str) -> dict:
        client = await self._get_client()
        fb_url = li_url = None
        deadline = asyncio.get_event_loop().time() + 20
        for base_url in _candidate_base_urls(domain):
            for path in SCAN_PATHS:
                if asyncio.get_event_loop().time() > deadline:
                    break
                if fb_url and li_url:
                    break
                page_url = f"{base_url}{path}"
                try:
                    resp = await asyncio.wait_for(client.get(page_url, headers={"User-Agent": _random_ua()}), timeout=5)
                    if resp.status_code != 200:
                        continue
                    pf, pl = _extract_from_html(resp.text, page_url)
                    if pf and not fb_url:
                        fb_url = pf
                    if pl and not li_url:
                        li_url = pl
                except Exception:
                    continue
        return {"facebook": fb_url, "linkedin": li_url}
