import asyncio
import re
from urllib.parse import urljoin

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
    r"https?://(?:www\.)?facebook\.com/(?!sharer|share|dialog|login|plugins|watch|video|events|groups|marketplace)([a-zA-Z0-9._]{3,})/?",
    re.I,
)
LINKEDIN_VALID_COMPANY = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/([a-zA-Z0-9_-]+)/?$", re.I)
LINKEDIN_INVALID = re.compile(r"linkedin\.com/(?:in|jobs|posts|pulse)/", re.I)
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.I)
SCAN_PATHS = ["/", "/contact", "/contact-us", "/kontakt", "/kontakty"]


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
        match = LINKEDIN_VALID_COMPANY.search(url.rstrip("/"))
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


def _extract_urls_from_html(html: str) -> set[str]:
    urls = set(re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', html, re.I))
    urls.update(re.findall(r'data-(?:href|url|link)=["\']([^"\']+)["\']', html, re.I))
    urls.update(re.findall(r'(?:fb(?:Url|_url|Link)|facebook(?:Url|Link))\s*[:=]\s*["\']([^"\']+)["\']', html, re.I))
    urls.update(re.findall(r'<meta[^>]+content=["\']([^"\']*facebook\.com[^"\']*)["\']', html, re.I))
    urls.update(re.findall(r'<meta[^>]+content=["\']([^"\']*linkedin\.com[^"\']*)["\']', html, re.I))
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

        urls_found = _extract_urls_from_html(html)
        normalized = "\n".join(urljoin(page_url, u) for u in urls_found)
        fb = extract_facebook(normalized)
        li = extract_linkedin_company(normalized)
        if fb or li:
            return {"facebook": fb, "linkedin": li}

    return {"facebook": None, "linkedin": None}
