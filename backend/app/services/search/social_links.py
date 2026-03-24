import re
from urllib.parse import urljoin, urlparse

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
LINKEDIN_VALID_COMPANY = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/([a-zA-Z0-9_-]+)/?$",
    re.I,
)
LINKEDIN_INVALID = re.compile(r"linkedin\.com/(?:in|jobs|posts|pulse)/", re.I)
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.I)


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


def scrape_social_from_website(website: str, soup: BeautifulSoup | None) -> dict[str, str | None]:
    if soup is None:
        return {"facebook": None, "linkedin": None}

    urls: list[str] = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not href:
            continue
        absolute = urljoin(website, href)
        urls.append(absolute)
    text = "\n".join(urls)
    return {"facebook": extract_facebook(text), "linkedin": extract_linkedin_company(text)}


def host_from_url(url: str) -> str:
    return urlparse(url).netloc.removeprefix("www.").lower()
