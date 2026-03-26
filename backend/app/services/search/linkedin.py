import asyncio
import random
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from app.services.contact.classifier import TitleClassifier
from app.services.search.serper import SerperClient

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

LEGAL_SUFFIXES = {"gmbh", "ag", "kg", "ltd", "limited", "llc", "inc", "corp", "co", "bv", "b.v", "srl", "s.a"}
MAX_COMPANY_TERMS = 2
MAX_SERPER_RESULTS = 6
LEADERSHIP_QUERY = 'site:linkedin.com/in/ "{term}" (CEO OR "Chief Executive Officer" OR Founder OR Owner OR President OR "Managing Director" OR "Executive Director" OR "General Manager" OR COO OR "Chief Operating Officer")'
PROCUREMENT_QUERY = 'site:linkedin.com/in/ "{term}" (Procurement OR Purchasing OR Sourcing OR "Head of Procurement" OR "Supply Chain")'
COMPANY_DISCOVER_QUERIES = (
    'site:linkedin.com/company/ "{term}"',
    '"{term}" "linkedin.com/company"',
    '"{term}" linkedin company',
)
CARD_SELECTORS = [
    'li.artdeco-list__item',
    '.org-people__profile-card',
    '.org-people-profiles-module__profile-item',
    '.scaffold-finite-scroll__content li',
    '[data-test-id="people-list"] li',
]
NAME_SELECTORS = [
    '.artdeco-entity-lockup__title a',
    '.artdeco-entity-lockup__title',
    '[data-test-id="member-name"]',
    '.org-people-profile-card__profile-title',
    '.org-people__profile-card-title',
    'a[href*="/in/"]',
]
TITLE_SELECTORS = [
    '.artdeco-entity-lockup__subtitle',
    '[data-test-id="member-title"]',
    '.artdeco-entity-lockup__caption',
    '.org-people-profile-card__profile-role',
    '.org-people__profile-card-subtitle',
    '.org-top-card-summary-info-list__info-item',
]
LINK_SELECTORS = ['a[href*="/in/"]']


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


class LinkedInPeopleFinder:
    def __init__(self, classifier: Optional[TitleClassifier] = None, serper_client: Optional[SerperClient] = None):
        self.classifier = classifier or TitleClassifier()
        self.serper = serper_client or SerperClient()
        self.last_diagnostics: dict[str, object] = {}

    async def find_key_people(
        self,
        company_name: str,
        linkedin_company_url: Optional[str] = None,
        company_website: Optional[str] = None,
    ) -> list[dict]:
        self.last_diagnostics = {"path_b": {"status": "not_attempted"}, "company_url": linkedin_company_url}
        company_terms = self._top_company_terms(self._build_company_terms(company_name, company_website))
        if linkedin_company_url:
            trusted_people, diagnostics = await self._path_b(linkedin_company_url)
            self.last_diagnostics["path_b"] = diagnostics
            if trusted_people:
                return self._deduplicate_and_filter(trusted_people)
        if not linkedin_company_url and company_terms:
            linkedin_company_url = await self._discover_company_url(company_terms)
            self.last_diagnostics["company_url"] = linkedin_company_url
        if linkedin_company_url:
            trusted_people, diagnostics = await self._path_b(linkedin_company_url)
            self.last_diagnostics["path_b"] = diagnostics
            if trusted_people:
                return self._deduplicate_and_filter(trusted_people)
        if not company_terms:
            return []

        leadership_people = await self._path_a(company_terms)
        all_people = leadership_people
        if len(leadership_people) < 2:
            all_people.extend(await self._path_c(company_terms))
        return self._deduplicate_and_filter(all_people)

    def _build_company_terms(self, company_name: str, company_website: Optional[str]) -> list[str]:
        terms: list[str] = []
        if self._is_useful_company_term(company_name):
            terms.append(company_name.strip())
            stripped_name = self._strip_legal_suffixes(company_name)
            if self._is_useful_company_term(stripped_name):
                terms.append(stripped_name)
        if company_website:
            parsed = urlparse(company_website if "://" in company_website else f"https://{company_website}")
            host = (parsed.netloc or parsed.path or "").lower().removeprefix("www.")
            host_root = host.split(".", 1)[0]
            for candidate in [host_root, host_root.replace("-", " "), self._strip_legal_suffixes(host_root.replace("-", " ")), host.replace(".", " ")]:
                candidate = candidate.strip()
                if self._is_useful_company_term(candidate):
                    terms.append(candidate)
        deduped: list[str] = []
        seen: set[str] = set()
        for term in terms:
            key = term.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(term)
        return deduped

    def _top_company_terms(self, company_terms: list[str]) -> list[str]:
        compact_seen: set[str] = set()
        prioritized: list[str] = []
        for term in company_terms:
            compact = re.sub(r"[^a-z0-9]+", "", term.lower())
            if compact in compact_seen:
                continue
            compact_seen.add(compact)
            prioritized.append(term)
            if len(prioritized) >= MAX_COMPANY_TERMS:
                break
        return prioritized

    def _is_useful_company_term(self, value: str | None) -> bool:
        if not value:
            return False
        normalized = value.strip().lower()
        if len(normalized) < 3 or normalized in {"about us", "unternehmen", "home", "about", "contact"}:
            return False
        stopwords = {"gmbh", "ltd", "llc", "inc", "co", "company", "group", "international", "the"}
        tokens = [token for token in re.split(r"[^a-z0-9]+", normalized) if token and token not in stopwords]
        return bool(tokens)

    def _strip_legal_suffixes(self, value: str) -> str:
        tokens = [token for token in re.split(r"\s+", (value or "").strip()) if token]
        stripped = [token for token in tokens if token.lower().strip(".,") not in LEGAL_SUFFIXES]
        return " ".join(stripped).strip()

    async def _discover_company_url(self, company_terms: list[str]) -> Optional[str]:
        for term in company_terms:
            for query in COMPANY_DISCOVER_QUERIES:
                try:
                    result = await self.serper.search(query.format(term=term), num=8)
                except Exception:
                    continue
                for item in result.get("organic", []):
                    normalized = self._normalize_company_url(item.get("link", "") or "")
                    if normalized:
                        return normalized
        return None

    def _normalize_company_url(self, url: str) -> Optional[str]:
        match = re.search(r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/([a-zA-Z0-9_-]+)', url, re.I)
        if not match:
            return None
        return f"https://www.linkedin.com/company/{match.group(1)}"

    def _normalize_title(self, title: str | None) -> str:
        normalized = re.sub(r"\s+", " ", (title or "")).strip()
        normalized = re.sub(r"\s+(?:at|@)\s+.+$", "", normalized, flags=re.I)
        normalized = normalized.replace("＆", "&")
        normalized = re.sub(r"\bco[\s-]?founder\s*&\s*ceo\b", "Co-Founder CEO", normalized, flags=re.I)
        normalized = re.sub(r"\bfounder\s*/\s*ceo\b", "Founder CEO", normalized, flags=re.I)
        normalized = re.sub(r"\bceo\s*/\s*founder\b", "CEO Founder", normalized, flags=re.I)
        return normalized

    async def _path_a(self, company_terms: list[str]) -> list[dict]:
        candidates: list[dict] = []
        for company_term in company_terms:
            query = LEADERSHIP_QUERY.format(term=company_term)
            try:
                result = await self.serper.search(query, num=MAX_SERPER_RESULTS)
            except Exception:
                continue
            for item in result.get("organic", []):
                title = item.get("title", "") or ""
                snippet = item.get("snippet", "") or ""
                link = item.get("link", "") or ""
                person = self._parse_serper_item(title, snippet, link)
                if person:
                    person["source"] = "path_a"
                    person["source_url"] = person.get("linkedin_personal_url")
                    person["source_context"] = f"{title} {snippet}".strip()
                    person["source_rank"] = 2
                    candidates.append(person)
            if len(candidates) >= MAX_SERPER_RESULTS:
                break
        return candidates

    async def _path_b(self, linkedin_company_url: Optional[str]) -> tuple[list[dict], dict]:
        diagnostics = {"status": "not_attempted", "source_url": linkedin_company_url}
        if not linkedin_company_url:
            diagnostics["status"] = "missing_company_url"
            return [], diagnostics

        candidates: list[dict] = []
        try:
            from playwright.async_api import async_playwright

            people_url = linkedin_company_url.rstrip("/") + "/people/"
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=_random_ua(), viewport={"width": 1280, "height": 900})
                page = await context.new_page()
                parsed_any_card = False
                saw_any_card = False

                for page_num in range(1, 4):
                    url = people_url + (f"?page={page_num}" if page_num > 1 else "")
                    try:
                        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
                        await page.wait_for_timeout(1000)
                        await self._perform_scroll(page)
                    except Exception:
                        diagnostics["status"] = "timeout"
                        diagnostics["source_url"] = url
                        await browser.close()
                        return candidates, diagnostics

                    page_html = await page.content()
                    lowered = page_html.lower()
                    if "authwall" in page.url.lower() or ("sign in" in lowered and "/in/" not in lowered and "/company/" in page.url.lower()):
                        diagnostics["status"] = "login_wall"
                        diagnostics["source_url"] = url
                        await browser.close()
                        return candidates, diagnostics
                    if "captcha" in lowered:
                        diagnostics["status"] = "captcha_or_block"
                        diagnostics["source_url"] = url
                        await browser.close()
                        return candidates, diagnostics

                    items = await self._query_cards(page)
                    if items:
                        saw_any_card = True
                    page_found = False
                    for item in items:
                        person = await self._extract_from_card(item, url)
                        if person:
                            parsed_any_card = True
                            ok, priority = self.classifier.classify(person.get("title", ""))
                            if ok:
                                person["priority"] = priority
                                person["source"] = "path_b"
                                person["source_url"] = url
                                person["source_rank"] = 0
                                candidates.append(person)
                                page_found = True
                    if not items:
                        break
                    if not page_found and page_num >= 2:
                        break

                await browser.close()
                if candidates:
                    diagnostics["status"] = "parsed"
                elif saw_any_card and not parsed_any_card:
                    diagnostics["status"] = "selector_miss"
                elif saw_any_card:
                    diagnostics["status"] = "no_cards"
                else:
                    diagnostics["status"] = "no_cards"
        except Exception:
            diagnostics["status"] = "selector_miss"
        return candidates, diagnostics

    async def _perform_scroll(self, page) -> None:
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, Math.max(window.innerHeight, 900));")
            await page.wait_for_timeout(700)

    async def _query_cards(self, page) -> list:
        collected = []
        seen = set()
        for selector in CARD_SELECTORS:
            try:
                nodes = await page.query_selector_all(selector)
            except Exception:
                continue
            for node in nodes:
                token = str(id(node))
                if token in seen:
                    continue
                seen.add(token)
                collected.append(node)
            if collected:
                break
        return collected

    async def _path_c(self, company_terms: list[str]) -> list[dict]:
        candidates: list[dict] = []
        for company_term in company_terms:
            query = PROCUREMENT_QUERY.format(term=company_term)
            try:
                result = await self.serper.search(query, num=MAX_SERPER_RESULTS)
            except Exception:
                continue
            for item in result.get("organic", []):
                title = item.get("title", "") or ""
                snippet = item.get("snippet", "") or ""
                link = item.get("link", "") or ""
                person = self._parse_serper_item(title, snippet, link)
                if person:
                    person["source"] = "path_c"
                    person["source_url"] = person.get("linkedin_personal_url")
                    person["source_context"] = f"{title} {snippet}".strip()
                    person["source_rank"] = 2
                    candidates.append(person)
            if len(candidates) >= MAX_SERPER_RESULTS:
                break
        return candidates

    async def _extract_first_text(self, card, selectors: list[str]) -> str | None:
        for selector in selectors:
            try:
                node = await card.query_selector(selector)
            except Exception:
                continue
            if not node:
                continue
            try:
                text = (await node.inner_text()).strip()
            except Exception:
                continue
            if text:
                return text
        return None

    async def _extract_first_link(self, card, selectors: list[str], page_url: str) -> str | None:
        for selector in selectors:
            try:
                node = await card.query_selector(selector)
            except Exception:
                continue
            if not node:
                continue
            try:
                href = await node.get_attribute("href")
            except Exception:
                continue
            if href:
                return urljoin(page_url, href)
        return None

    async def _extract_from_card(self, card, page_url: str) -> Optional[dict]:
        try:
            person_name = await self._extract_first_text(card, NAME_SELECTORS)
            job_title = self._normalize_title(await self._extract_first_text(card, TITLE_SELECTORS))
            li_url = await self._extract_first_link(card, LINK_SELECTORS, page_url)
            if li_url and "linkedin.com/in/" not in li_url:
                li_url = None
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
            person_name, job_title = m.group(1).strip(), self._normalize_title(m.group(2).strip())
        else:
            parts = re.split(r'\s*[-–]\s*', title, maxsplit=2)
            if len(parts) < 2:
                return None
            person_name, job_title = parts[0].strip(), self._normalize_title(parts[1].strip())
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
        for person in people:
            url = person.get("linkedin_personal_url") or ""
            normalized_title = self._normalize_title(person.get("title", ""))
            person["title"] = normalized_title
            name_key = ((person.get("person_name") or "").lower(), normalized_title.lower()[:40])
            if url and url in seen_urls:
                continue
            if not url and name_key in seen_names:
                continue
            if url:
                seen_urls.add(url)
            seen_names.add(name_key)
            if _is_valid_person_name(person.get("person_name", "")):
                result.append(person)
        return sorted(result, key=lambda item: (item.get("source_rank", 9), item.get("priority", 99)))


def _is_valid_person_name(name: str) -> bool:
    if not name or len(name) < 3 or len(name) > 60:
        return False
    invalid = [
        r'^[A-Za-z]+ Contact$',
        r'^[A-Za-z]+ (Info|Team|Admin|Support|Sales|Enquiry)$',
        r'^(Contact|Info|Admin|Sales|Support|Hello|General)$',
        r'^\w{1,2}$',
        r'^\d+',
    ]
    return not any(re.match(pattern, name, re.I) for pattern in invalid) and len(name.strip().split()) >= 2
