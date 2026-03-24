import asyncio
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

FACEBOOK_BLACKLIST_PATTERNS = [
    r"facebook\.com/sharer",
    r"facebook\.com/share",
    r"facebook\.com/dialog/",
    r"facebook\.com/login",
    r"facebook\.com/plugins",
    r"\?u=",
    r"facebook\.com/\d{15,}",
]
FACEBOOK_BLACKLIST = re.compile("|".join(FACEBOOK_BLACKLIST_PATTERNS), re.I)
FACEBOOK_VALID_PATTERN = re.compile(
    r"https?://(?:www\.)?facebook\.com/(?!sharer|share|dialog|login|plugins|watch|video|events|groups|marketplace)([a-zA-Z0-9._-]{3,})",
    re.I,
)
LINKEDIN_VALID_COMPANY = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/([a-zA-Z0-9_-]+)(?:[/?#].*)?$",
    re.I,
)
LINKEDIN_INVALID = re.compile(r"linkedin\.com/(?:in|jobs|posts|pulse)/", re.I)
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.I)
SCAN_PATHS = ["/", "/contact", "/contact-us", "/about", "/about-us"]


def _normalize_candidate_url(base_url: str, raw_url: str) -> str | None:
    if not raw_url:
        return None
    candidate = raw_url.strip()
    if not candidate:
        return None

    if candidate.startswith("//"):
        candidate = f"https:{candidate}"
    elif candidate.startswith("/"):
        if candidate.startswith("/company/"):
            candidate = f"https://www.linkedin.com{candidate}"
        else:
            candidate = urljoin(base_url, candidate)
    elif not re.match(r"^https?://", candidate, re.I):
        candidate = urljoin(base_url, candidate)

    parsed = urlparse(candidate)
    if not parsed.netloc:
        return None
    return f"{parsed.scheme or 'https'}://{parsed.netloc}{parsed.path}" + (f"?{parsed.query}" if parsed.query else "")


def find_all_urls(text: str) -> list[str]:
    return URL_PATTERN.findall(text or "")


def extract_facebook(text: str) -> str | None:
    for url in find_all_urls(text):
        if FACEBOOK_BLACKLIST.search(url):
            continue
        match = FACEBOOK_VALID_PATTERN.search(url)
        if match:
            return f"https://www.facebook.com/{match.group(1)}"
    return None


def extract_linkedin_company(text: str) -> str | None:
    for url in find_all_urls(text):
        if LINKEDIN_INVALID.search(url):
            continue
        match = LINKEDIN_VALID_COMPANY.search(url)
        if match:
            return f"https://www.linkedin.com/company/{match.group(1)}"
    return None


async def _fetch_html(url: str, timeout: float = 5.0) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 LeadGenBot/1.0"})
            response.raise_for_status()
            return response.text
    except Exception:
        return None


def _extract_urls_from_dom(html: str, base_url: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: set[str] = set()

    for node in soup.select("a[href], link[href]"):
        normalized = _normalize_candidate_url(base_url, node.get("href"))
        if normalized:
            urls.add(normalized)

    for node in soup.select("meta[content]"):
        normalized = _normalize_candidate_url(base_url, node.get("content"))
        if normalized and ("facebook.com" in normalized.lower() or "linkedin.com" in normalized.lower()):
            urls.add(normalized)

    for attr_pattern in [r'data-(?:href|url|link)=["\']([^"\']+)["\']', r'(?:fb(?:Url|_url|Link)|facebook(?:Url|Link)|linkedin(?:Url|Link))\s*[:=]\s*["\']([^"\']+)["\']']:
        for raw in re.findall(attr_pattern, html, re.I):
            normalized = _normalize_candidate_url(base_url, raw)
            if normalized:
                urls.add(normalized)

    for raw in find_all_urls(html):
        normalized = _normalize_candidate_url(base_url, raw)
        if normalized:
            urls.add(normalized)

    return urls


async def scrape_social_from_website(website: str, homepage_soup: BeautifulSoup | None) -> dict[str, str | None]:
    for path in SCAN_PATHS:
        page_url = urljoin(website, path)
        if path == "/" and homepage_soup is not None:
            html = str(homepage_soup)
        else:
            try:
                html = await asyncio.wait_for(_fetch_html(page_url, timeout=5.0), timeout=5.0)
            except Exception:
                html = None
        if not html:
            continue

        urls_found = _extract_urls_from_dom(html, page_url)
        normalized_text = "\n".join(urls_found)
        fb = extract_facebook(normalized_text)
        li = extract_linkedin_company(normalized_text)
        if fb or li:
            return {"facebook": fb, "linkedin": li}

    return {"facebook": None, "linkedin": None}
