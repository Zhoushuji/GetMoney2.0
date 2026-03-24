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
CONTACT_PATHS = ["/", "/contact", "/contact-us", "/kontakt", "/kontakty", "/get-in-touch", "/reach-us"]


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


async def _fetch_soup(url: str, timeout: float = 5.0) -> BeautifulSoup | None:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 LeadGenBot/1.0"})
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
    except Exception:
        return None


async def scrape_social_from_website(website: str, homepage_soup: BeautifulSoup | None) -> dict[str, str | None]:
    linkedin = None
    if homepage_soup is not None:
        homepage_links = [urljoin(website, href) for href in [a.get("href") for a in homepage_soup.select("a[href]")] if href]
        linkedin = extract_linkedin_company("\n".join(homepage_links))

    async def scan_page(path: str) -> str | None:
        url = urljoin(website, path)
        soup = homepage_soup if path == "/" and homepage_soup is not None else await _fetch_soup(url, timeout=5.0)
        if soup is None:
            return None
        hrefs = [urljoin(url, href) for href in [a.get("href") for a in soup.select("a[href]")] if href]
        text = soup.get_text(" ", strip=True)
        return extract_facebook("\n".join(hrefs) + "\n" + text)

    facebook = None
    for path in CONTACT_PATHS:
        try:
            facebook = await asyncio.wait_for(scan_page(path), timeout=5.0)
        except Exception:
            facebook = None
        if facebook:
            break

    return {"facebook": facebook, "linkedin": linkedin}
