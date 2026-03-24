import asyncio
import random
import re
from typing import Optional

from app.services.contact.classifier import TitleClassifier
from app.services.search.serper import call_serper

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

TITLE_SEARCH_GROUPS = [
    ["CEO", "Chief Executive Officer", "Founder", "Owner", "President"],
    ["Managing Director", "Director General", "Executive Director"],
    ["General Manager", "COO", "Chief Operating Officer"],
    ["Procurement Manager", "Purchasing Manager", "Sourcing Manager", "Head of Procurement", "Supply Chain Manager"],
]


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


class LinkedInPeopleFinder:
    def __init__(self, classifier: Optional[TitleClassifier] = None):
        self.classifier = classifier or TitleClassifier()

    async def find_key_people(self, company_name: str, linkedin_company_url: Optional[str] = None) -> list[dict]:
        tasks = [
            asyncio.create_task(self._path_a(company_name)),
            asyncio.create_task(self._path_b(linkedin_company_url)),
            asyncio.create_task(self._path_c(company_name)),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_people: list[dict] = []
        for r in results:
            if isinstance(r, list):
                all_people.extend(r)
        return self._deduplicate_and_filter(all_people)

    async def _path_a(self, company_name: str) -> list[dict]:
        candidates: list[dict] = []
        for group in TITLE_SEARCH_GROUPS:
            primary = group[0]
            for q in [f'site:linkedin.com/in/ "{company_name}" "{primary}"', f'"{company_name}" "{primary}" linkedin profile']:
                try:
                    result = await call_serper(q, num=10)
                    for item in result.get("organic", []):
                        person = self._parse_serper_item(item.get("title", ""), item.get("snippet", ""), item.get("link", ""))
                        if person:
                            person["source"] = "path_a"
                            candidates.append(person)
                    await asyncio.sleep(0.3)
                except Exception:
                    continue
        return candidates

    async def _path_b(self, linkedin_company_url: Optional[str]) -> list[dict]:
        if not linkedin_company_url:
            return []
        candidates: list[dict] = []
        try:
            from playwright.async_api import async_playwright

            people_url = linkedin_company_url.rstrip("/") + "/people/"
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=_random_ua(), viewport={"width": 1280, "height": 800})
                page = await context.new_page()
                for page_num in range(1, 4):
                    url = people_url + (f"?page={page_num}" if page_num > 1 else "")
                    try:
                        await page.goto(url, timeout=15000, wait_until="networkidle")
                        await page.wait_for_selector('li.artdeco-list__item,.org-people__item', timeout=8000)
                    except Exception:
                        break
                    items = await page.query_selector_all('li.artdeco-list__item,.org-people__item')
                    page_found = False
                    for item in items:
                        person = await self._extract_from_card(item)
                        if person:
                            ok, priority = self.classifier.classify(person.get("title", ""))
                            if ok:
                                person["priority"] = priority
                                person["source"] = "path_b"
                                candidates.append(person)
                                page_found = True
                    if not page_found:
                        break
                await browser.close()
        except Exception:
            pass
        return candidates

    async def _path_c(self, company_name: str) -> list[dict]:
        candidates: list[dict] = []
        queries = [
            f'site:linkedin.com/in/ "{company_name}" (CEO OR "Managing Director" OR "General Manager" OR Founder OR Owner OR President)',
            f'site:linkedin.com/in/ "{company_name}" (Procurement OR Purchasing OR Sourcing OR "Supply Chain")',
        ]
        for q in queries:
            try:
                result = await call_serper(q, num=10)
                for item in result.get("organic", []):
                    person = self._parse_serper_item(item.get("title", ""), item.get("snippet", ""), item.get("link", ""))
                    if person:
                        person["source"] = "path_c"
                        candidates.append(person)
                await asyncio.sleep(0.3)
            except Exception:
                continue
        return candidates

    async def _extract_from_card(self, card) -> Optional[dict]:
        try:
            name_el = await card.query_selector('.artdeco-entity-lockup__title,[data-test-id="member-name"]')
            person_name = (await name_el.inner_text()).strip() if name_el else ""
            title_el = await card.query_selector('.artdeco-entity-lockup__subtitle,[data-test-id="member-title"]')
            job_title = (await title_el.inner_text()).strip() if title_el else ""
            link_el = await card.query_selector('a[href*="linkedin.com/in/"]')
            li_url = await link_el.get_attribute("href") if link_el else None
            if not person_name or not _is_valid_person_name(person_name):
                return None
            return {"person_name": person_name, "title": job_title, "linkedin_personal_url": li_url}
        except Exception:
            return None

    def _parse_serper_item(self, title: str, snippet: str, link: str) -> Optional[dict]:
        if not re.match(r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_\-]+', link):
            return None
        title = re.sub(r'\s*[\|·]\s*LinkedIn\s*$', '', title, flags=re.I).strip()
        m = re.match(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-–]\s*(.+?)(?:\s+(?:at|@|–|-)\s+.+)?$', title)
        if m:
            person_name, job_title = m.group(1).strip(), m.group(2).strip()
        else:
            parts = re.split(r'\s*[-–]\s*', title, maxsplit=2)
            if len(parts) < 2:
                return None
            person_name, job_title = parts[0].strip(), parts[1].strip()
        if not _is_valid_person_name(person_name):
            return None
        ok, priority = self.classifier.classify(job_title)
        if not ok:
            return None
        return {"person_name": person_name, "title": job_title, "linkedin_personal_url": link, "priority": priority}

    def _deduplicate_and_filter(self, people: list[dict]) -> list[dict]:
        seen_urls: set[str] = set()
        seen_names: set[tuple] = set()
        result: list[dict] = []
        for p in people:
            url = p.get("linkedin_personal_url", "")
            name_key = (p.get("person_name", "").lower(), p.get("title", "").lower()[:20])
            if url and url in seen_urls:
                continue
            if not url and name_key in seen_names:
                continue
            if url:
                seen_urls.add(url)
            seen_names.add(name_key)
            if _is_valid_person_name(p.get("person_name", "")):
                result.append(p)
        return sorted(result, key=lambda x: x.get("priority", 99))


def _is_valid_person_name(name: str) -> bool:
    if not name or len(name) < 3 or len(name) > 60:
        return False
    invalid = [
        r'^[A-Za-z]+ Contact$', r'^[A-Za-z]+ (Info|Team|Admin|Support|Sales|Enquiry)$', r'^(Contact|Info|Admin|Sales|Support|Hello|General)$', r'^\w{1,2}$', r'^\d+'
    ]
    return not any(re.match(p, name, re.I) for p in invalid) and len(name.strip().split()) >= 2
