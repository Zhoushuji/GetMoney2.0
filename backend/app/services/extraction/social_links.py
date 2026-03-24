import asyncio
import random
import re
from typing import Optional

import httpx

from app.services.search.serper import call_serper

FB_BLACKLIST = [
    r"facebook\.com/sharer", r"facebook\.com/share", r"facebook\.com/dialog/", r"facebook\.com/login", r"facebook\.com/plugins", r"facebook\.com/tr\?",
    r"\?u=", r"/watch/", r"/events/", r"/groups/", r"/marketplace/", r"/hashtag/", r"/pages/category/", r"facebook\.com/?$", r"facebook\.com/home",
]

FB_VALID = re.compile(r"https?://(?:www\.)?facebook\.com/(?!sharer|share|dialog|login|plugins|watch|events|groups|marketplace|hashtag|home|pages/category)([a-zA-Z0-9._]{3,100})/?(?:\?.*)?$")
LI_VALID_COMPANY = re.compile(r"https?://(?:www\.)?linkedin\.com/company/([a-zA-Z0-9_\-]{2,100})/?(?:\?.*)?$")
LI_BLACKLIST = [r"linkedin\.com/in/", r"linkedin\.com/jobs/", r"linkedin\.com/posts/", r"linkedin\.com/pulse/", r"linkedin\.com/school/", r"linkedin\.com/showcase/"]
SCAN_PATHS = ["/", "/contact", "/contact-us", "/kontakt", "/kontakty", "/contacto", "/sobre-nosotros", "/about", "/about-us"]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


def _is_valid_fb(url: str) -> bool:
    return bool(url) and not any(re.search(p, url, re.I) for p in FB_BLACKLIST) and bool(FB_VALID.match(url))


def _is_valid_li_company(url: str) -> bool:
    return bool(url) and not any(re.search(p, url, re.I) for p in LI_BLACKLIST) and bool(LI_VALID_COMPANY.match(url))


def _extract_from_html(html: str) -> tuple[Optional[str], Optional[str]]:
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

    fb = next((u for u in urls if _is_valid_fb(u)), None)
    li = next((u for u in urls if _is_valid_li_company(u)), None)
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
        track_a, track_b = await asyncio.gather(self._track_a(company_name), self._track_b(domain), return_exceptions=True)
        if isinstance(track_a, Exception):
            track_a = {}
        if isinstance(track_b, Exception):
            track_b = {}
        return {"facebook": track_a.get("facebook") or track_b.get("facebook"), "linkedin": track_a.get("linkedin") or track_b.get("linkedin")}

    async def _track_a(self, company_name: str) -> dict:
        fb_url = li_url = None
        try:
            for q in [f'"{company_name}" site:facebook.com -sharer -dialog', f'"{company_name}" site:facebook.com']:
                result = await call_serper(q, num=5)
                for item in result.get("organic", []):
                    if _is_valid_fb(item.get("link", "")):
                        fb_url = item["link"]
                        break
                if fb_url:
                    break
        except Exception:
            pass
        try:
            for q in [f'"{company_name}" site:linkedin.com/company', f'site:linkedin.com/company "{company_name}"']:
                result = await call_serper(q, num=5)
                for item in result.get("organic", []):
                    if _is_valid_li_company(item.get("link", "")):
                        li_url = item["link"]
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
        for path in SCAN_PATHS:
            if asyncio.get_event_loop().time() > deadline:
                break
            if fb_url and li_url:
                break
            try:
                resp = await asyncio.wait_for(client.get(f"https://{domain}{path}", headers={"User-Agent": _random_ua()}), timeout=5)
                if resp.status_code != 200:
                    continue
                pf, pl = _extract_from_html(resp.text)
                if pf and not fb_url:
                    fb_url = pf
                if pl and not li_url:
                    li_url = pl
            except Exception:
                continue
        return {"facebook": fb_url, "linkedin": li_url}
