import asyncio
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from uuid import uuid4

from app.schemas.contact import ContactRead
from app.services.contact.classifier import TitleClassifier
from app.services.search.linkedin import LinkedInPeopleFinder
from app.services.search.serper import SerperClient

PHONE_NEAR_WA_WINDOW = 50
DIAGNOSTIC_FAILED_STATUSES = {"login_wall", "captcha_or_block", "selector_miss"}
DIAGNOSTIC_TIMEOUT_STATUSES = {"timeout"}
INVALID_PERSON_NAME_PATTERNS = [
    re.compile(r"^[A-Z][a-z]+ Contact$"),
    re.compile(r"^[A-Z][a-z]+ (Info|Team|Admin|Support|Sales)$"),
    re.compile(r"^\w{1,3}$"),
]
INVALID_LINKEDIN_PATTERNS = [
    re.compile(r"linkedin\.com/in/[a-z]+-contact$", re.I),
    re.compile(r"linkedin\.com/in/[a-z]+-info$", re.I),
    re.compile(r"linkedin\.com/company/", re.I),
]
INVALID_EMAIL_AS_PERSONAL = [
    re.compile(r"^(contact|info|hello|support|sales|admin|office|mail|enquiry|query)@", re.I),
]
EXCLUDED_GENERAL_EMAIL_PATTERNS = [
    re.compile(r"^(sales|marketing|support|hr|career|jobs)@", re.I),
]
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_PATTERN = re.compile(r"(?:\+\d[\d\s()-]{8,}\d)")
WA_ME_PATTERN = re.compile(r"wa\.me/(\d{10,15})", re.I)
WA_API_PATTERN = re.compile(r"api\.whatsapp\.com/send\?phone=(\d{10,15})", re.I)
CONTACT_SCAN_PATHS = ["/", "/about", "/about-us", "/team", "/leadership", "/contact", "/contact-us"]


class LinkedInPeopleDiagnosticError(Exception):
    def __init__(self, status: str, details: dict | None = None):
        self.status = status
        self.details = details or {}
        message = self._message_for(status)
        super().__init__(message)

    @staticmethod
    def _message_for(status: str) -> str:
        messages = {
            "login_wall": "LinkedIn people page hit a login wall",
            "captcha_or_block": "LinkedIn people page was blocked by captcha",
            "selector_miss": "LinkedIn people page layout changed and no supported selectors matched",
            "timeout": "LinkedIn people page timed out",
        }
        return messages.get(status, f"LinkedIn people page failed with status={status}")



class ContactIntelligenceService:
    def __init__(self) -> None:
        self.classifier = TitleClassifier()
        self.serper = SerperClient()
        self.linkedin_people_finder = LinkedInPeopleFinder(classifier=self.classifier, serper_client=self.serper)

    def _soup_from_html(self, html: str):
        return BeautifulSoup(html, "html.parser")

    async def find_contacts(self, lead) -> list[ContactRead]:
        return await self.find_decision_makers(lead)

    async def find_decision_makers(self, lead) -> list[ContactRead]:
        if self._is_demo_lead(lead):
            return []
        company_name = lead.company_name or ""
        pages = await self._fetch_site_pages(lead.website)
        combined_html = "\n".join(html for _, html in pages)
        soup = self._soup_from_html(combined_html) if combined_html else None
        source_urls = [url for url, _ in pages]
        potential_contacts = self._extract_potential_contacts(lead.website, soup)
        website_people = self._extract_linkedin_people(soup, company_name)
        verified_website_people = self._verify_people(website_people, company_name, lead.website)
        if verified_website_people:
            contact = self._build_contact(lead, verified_website_people, potential_contacts, source_urls=source_urls)
            return [contact] if contact else []

        linkedin_company_url = getattr(lead, "linkedin_url", None) or self._extract_linkedin_company_url(pages)
        resolved_linkedin_company_url = linkedin_company_url
        linkedin_path_diagnostics: dict | None = None
        linkedin_people_candidates: list[dict] = []
        if company_name or linkedin_company_url or lead.website:
            linkedin_people_candidates = await self.linkedin_people_finder.find_key_people(company_name, linkedin_company_url, lead.website)
            resolved_linkedin_company_url = self.linkedin_people_finder.last_diagnostics.get("company_url") or linkedin_company_url
            linkedin_path_diagnostics = dict(self.linkedin_people_finder.last_diagnostics.get("path_b") or {})
        linkedin_people = self._merge_people(website_people, linkedin_people_candidates)

        if not linkedin_people and company_name and not linkedin_company_url:
            linkedin_people = self._merge_people(linkedin_people, await self._search_linkedin_people_via_google(company_name))
        trusted_people = [person for person in linkedin_people if self._is_trusted_source(person)]
        verified_people = self._verify_people(trusted_people or linkedin_people, company_name, lead.website)
        if trusted_people and not verified_people:
            verified_people = self._verify_people(linkedin_people, company_name, lead.website)
        contact = self._build_contact(lead, verified_people, potential_contacts, source_urls=source_urls)
        if contact:
            return [contact]

        self._raise_for_linkedin_path_failure(
            linkedin_path_diagnostics,
            company_name=company_name,
            website=lead.website,
            linkedin_company_url=resolved_linkedin_company_url,
        )
        return []

    async def _search_linkedin_people_via_google(self, company_name: str) -> list[dict]:
        people: list[dict] = []
        seen: set[str] = set()
        query = f'"{company_name}" site:linkedin.com/in (owner OR "managing director" OR ceo OR founder)'
        try:
            result = await self.serper.search(query=query, gl="us", hl="en", num=6)
        except Exception:
            return people
        for item in result.get("organic", []):
            link = item.get("link", "")
            if "linkedin.com/in/" not in link or link in seen:
                continue
            seen.add(link)
            title = item.get("title", "") or ""
            snippet = item.get("snippet", "") or ""
            role_title = self._guess_role_title_from_text(f"{title} {snippet}")
            person_name = self._guess_person_name_from_title(title)
            people.append({
                "person_name": person_name,
                "title": role_title,
                "linkedin_personal_url": link,
                "source": "legacy_google",
                "source_url": link,
                "source_context": f"{title} {snippet}".strip(),
                "source_rank": 3,
            })
        return people

    def _guess_role_title_from_text(self, text: str) -> str | None:
        mapping = [
            (r"\bmanaging director\b", "Managing Director"),
            (r"\bchief executive officer\b|\bceo\b", "CEO"),
            (r"\bco-founder\b", "Co-Founder"),
            (r"\bfounder\b", "Founder"),
            (r"\bowner\b", "Owner"),
        ]
        for pattern, role in mapping:
            if re.search(pattern, text, re.I):
                return role
        return None

    def _guess_person_name_from_title(self, title: str) -> str | None:
        chunks = [part.strip() for part in re.split(r"[-|,]", title or "") if part.strip()]
        for chunk in chunks:
            if re.search(r"\b(owner|director|ceo|founder|linkedin)\b", chunk, re.I):
                continue
            if re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}$", chunk):
                return chunk
        return None

    def _normalize_role_title(self, title: str | None) -> str:
        normalized = re.sub(r"\s+", " ", (title or "")).strip()
        normalized = re.sub(r"\s+(?:at|@)\s+.+$", "", normalized, flags=re.I)
        normalized = normalized.replace("＆", "&")
        normalized = re.sub(r"\bco[\s-]?founder\s*&\s*ceo\b", "Co-Founder & CEO", normalized, flags=re.I)
        normalized = re.sub(r"\bfounder\s*/\s*ceo\b", "Founder / CEO", normalized, flags=re.I)
        normalized = re.sub(r"\bceo\s*/\s*founder\b", "CEO / Founder", normalized, flags=re.I)
        return normalized

    async def find_potential_contacts(self, lead) -> dict[str, list[str]]:
        if self._is_demo_lead(lead):
            source_urls = [lead.website] if getattr(lead, "website", None) else []
            return {"emails": [], "generic_emails": [], "phones": [], "whatsapp": [], "all": [], "source_urls": source_urls}
        pages = await self._fetch_site_pages(lead.website)
        merged = {"emails": set(), "generic_emails": set(), "phones": set(), "whatsapp": set(), "all": set(), "source_urls": []}
        for page_url, html in pages:
            soup = self._soup_from_html(html)
            extracted = self._extract_potential_contacts(lead.website, soup)
            merged["emails"].update(extracted.get("emails", []))
            merged["generic_emails"].update(extracted.get("generic_emails", []))
            merged["phones"].update(extracted.get("phones", []))
            merged["whatsapp"].update(extracted.get("whatsapp", []))
            merged["all"].update(extracted.get("all", []))
            merged["source_urls"].append(page_url)
        return {
            "emails": sorted(merged["emails"]),
            "generic_emails": sorted(merged["generic_emails"]),
            "phones": sorted(merged["phones"]),
            "whatsapp": sorted(merged["whatsapp"]),
            "all": sorted(merged["all"]),
            "source_urls": merged["source_urls"],
        }

    async def _fetch_site_pages(self, website: str | None) -> list[tuple[str, str]]:
        if not website:
            return []
        pages: list[tuple[str, str]] = []
        for path in CONTACT_SCAN_PATHS:
            page_url = urljoin(website, path)
            html = await self._fetch_html(page_url)
            if html:
                pages.append((page_url, html))
        return pages

    async def _fetch_html(self, url: str | None) -> str | None:
        if not url:
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 LeadGenBot/1.0"})
                response.raise_for_status()
                return response.text
        except Exception:
            return None

    def _extract_linkedin_company_url(self, pages: list[tuple[str, str]]) -> str | None:
        seen: set[str] = set()
        for page_url, html in pages:
            soup = self._soup_from_html(html)
            for node in soup.select("a[href], link[href], meta[content]"):
                raw = node.get("href") or node.get("content") or ""
                if "linkedin.com/company/" not in raw.lower() and "/company/" not in raw.lower():
                    continue
                candidate = raw.strip()
                if candidate.startswith("//"):
                    candidate = f"https:{candidate}"
                elif candidate.startswith("/"):
                    candidate = urljoin(page_url, candidate)
                elif not re.match(r"^https?://", candidate, re.I):
                    candidate = urljoin(page_url, candidate)
                match = re.search(r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/([a-zA-Z0-9_-]+)', candidate, re.I)
                if not match:
                    continue
                normalized = f"https://www.linkedin.com/company/{match.group(1)}"
                if normalized in seen:
                    continue
                seen.add(normalized)
                return normalized
        return None

    def _extract_linkedin_people(self, soup: BeautifulSoup | None, company_name: str) -> list[dict]:
        if soup is None:
            return []
        candidates: list[dict] = []
        seen = set()
        for anchor in soup.select('a[href*="linkedin.com/in/"]'):
            href = anchor.get("href")
            text = anchor.get_text(" ", strip=True)
            if not href or href in seen:
                continue
            seen.add(href)
            container_text = anchor.parent.get_text(" ", strip=True) if anchor.parent else text
            title = container_text.replace(text, "").strip(" -|:") or None
            candidates.append({
                "person_name": text or None,
                "title": title,
                "linkedin_personal_url": href,
                "source": "website",
                "source_url": href,
                "source_rank": 0,
            })
        return candidates

    def _merge_people(self, *groups: list[dict]) -> list[dict]:
        merged: list[dict] = []
        seen_urls: set[str] = set()
        seen_names: set[tuple[str, str]] = set()
        for group in groups:
            for person in group:
                url = (person.get("linkedin_personal_url") or "").strip()
                name_key = (
                    (person.get("person_name") or "").strip().lower(),
                    (person.get("title") or "").strip().lower(),
                )
                if url:
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                elif name_key in seen_names:
                    continue
                seen_names.add(name_key)
                merged.append(person)
        return merged

    def _verify_people(self, people: list[dict], company_name: str, website: str | None = None) -> list[dict]:
        verified: list[dict] = []
        company_tokens = self._company_tokens(company_name, website)
        for person in people:
            name = person.get("person_name") or ""
            title = self._normalize_role_title(person.get("title") or "")
            linkedin = person.get("linkedin_personal_url") or ""
            source = person.get("source") or ""
            if any(pattern.search(name) for pattern in INVALID_PERSON_NAME_PATTERNS):
                continue
            if any(pattern.search(linkedin) for pattern in INVALID_LINKEDIN_PATTERNS):
                continue
            is_allowed, priority = self.classifier.classify(title)
            if not is_allowed:
                continue
            person["title"] = title
            person["priority"] = priority
            if source not in {"website", "path_b"}:
                context = f"{name} {title} {linkedin} {person.get('source_context') or ''}".lower()
                token_hits = sum(1 for token in company_tokens if token in context)
                required_hits = 1 if len(company_tokens) == 1 else 2
                if company_tokens and token_hits < min(required_hits, len(company_tokens)):
                    continue
            verified.append(person)
        return sorted(verified, key=lambda item: (item.get("source_rank") or 9, item.get("priority") or 999))

    def _company_tokens(self, company_name: str, website: str | None = None) -> list[str]:
        tokens: list[str] = []
        for raw in [company_name or "", self._website_brand(website)]:
            for token in re.split(r"[^a-z0-9]+", raw.lower()):
                if len(token) < 3:
                    continue
                if token in {"about", "unternehmen", "contact", "home", "company", "group", "the", "inc", "llc", "ltd", "gmbh"}:
                    continue
                tokens.append(token)
        deduped: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            deduped.append(token)
        return deduped

    def _website_brand(self, website: str | None) -> str:
        if not website:
            return ""
        parsed = urlparse(website if "://" in website else f"https://{website}")
        host = (parsed.netloc or parsed.path or "").lower().removeprefix("www.")
        if not host:
            return ""
        return host.split(".", 1)[0].replace("-", " ")

    def _is_trusted_source(self, person: dict) -> bool:
        return (person.get("source") or "") in {"website", "path_b"}

    def _is_demo_lead(self, lead) -> bool:
        raw_data = getattr(lead, "raw_data", None) or {}
        if raw_data.get("demo_mode"):
            return True
        if getattr(lead, "source", None) == "demo":
            return True
        website = (getattr(lead, "website", None) or "").strip()
        if not website:
            return False
        parsed = urlparse(website if "://" in website else f"https://{website}")
        host = (parsed.netloc or parsed.path or "").lower().removeprefix("www.")
        return host == "example.com" and parsed.path.startswith("/demo/")

    def _raise_for_linkedin_path_failure(
        self,
        diagnostics: dict | None,
        *,
        company_name: str,
        website: str | None,
        linkedin_company_url: str | None,
    ) -> None:
        if not diagnostics:
            return
        status = (diagnostics.get("status") or "").strip()
        if status in DIAGNOSTIC_TIMEOUT_STATUSES:
            raise LinkedInPeopleDiagnosticError(
                "timeout",
                {
                    "company_name": company_name,
                    "website": website,
                    "linkedin_company_url": linkedin_company_url,
                    "linkedin_path_diagnostics": diagnostics,
                },
            )
        if status in DIAGNOSTIC_FAILED_STATUSES:
            raise LinkedInPeopleDiagnosticError(
                status,
                {
                    "company_name": company_name,
                    "website": website,
                    "linkedin_company_url": linkedin_company_url,
                    "linkedin_path_diagnostics": diagnostics,
                },
            )

    def _build_contact(self, lead, verified_people: list[dict], potential_contacts: dict[str, list[str]], source_urls: list[str] | None = None) -> ContactRead | None:
        chosen = verified_people[0] if verified_people else None
        if chosen is None:
            return None

        personal_email = None
        work_email = None
        phone = None
        whatsapp_list = potential_contacts.get("whatsapp") or []
        whatsapp = whatsapp_list[0] if whatsapp_list else None
        first, _, last = (chosen.get("person_name") or "").partition(" ")
        for email in potential_contacts.get("emails", []):
            local = email.split("@", 1)[0].lower()
            if any(pattern.search(local + "@") for pattern in INVALID_EMAIL_AS_PERSONAL):
                continue
            if first.lower() in local or (last and last.lower() in local):
                personal_email = email
                break
        if not personal_email:
            work_email = next(iter(potential_contacts.get("emails", [])), None)
        phone = next(iter(potential_contacts.get("phones", [])), None)
        resolved_source_urls = list(source_urls or ([lead.website] if lead.website else []))
        for candidate_url in [chosen.get("source_url"), chosen.get("linkedin_personal_url")]:
            if candidate_url and candidate_url not in resolved_source_urls:
                resolved_source_urls.append(candidate_url)

        return ContactRead(
            id=uuid4(),
            lead_id=lead.id,
            person_name=chosen.get("person_name") if chosen else None,
            title=chosen.get("title") if chosen else None,
            priority=chosen.get("priority") if chosen else None,
            personal_email=personal_email,
            work_email=work_email,
            linkedin_personal_url=chosen.get("linkedin_personal_url") if chosen else None,
            phone=phone,
            whatsapp=whatsapp,
            potential_contacts=None,
            source_urls=resolved_source_urls,
            verified_at=None,
        )

    def _extract_potential_contacts(self, website: str | None, soup: BeautifulSoup | None) -> dict[str, list[str]]:
        if soup is None:
            return {"emails": [], "phones": [], "whatsapp": [], "all": []}
        text = soup.get_text(" ", strip=True)
        hrefs = "\n".join(anchor.get("href") or "" for anchor in soup.select("a[href]"))
        emails = sorted({email for email in EMAIL_PATTERN.findall(text)})
        generic_emails = sorted([
            email
            for email in emails
            if any(pattern.search(email) for pattern in INVALID_EMAIL_AS_PERSONAL)
            and not any(pattern.search(email) for pattern in EXCLUDED_GENERAL_EMAIL_PATTERNS)
        ])
        phones = sorted({self._normalize_phone(phone) for phone in PHONE_PATTERN.findall(text) if self._normalize_phone(phone)})
        whatsapp = self._extract_whatsapp(text + "\n" + hrefs)
        generic_contacts = []
        filtered_for_generic = [email for email in emails if not any(pattern.search(email) for pattern in EXCLUDED_GENERAL_EMAIL_PATTERNS)]
        for email in filtered_for_generic:
            generic_contacts.append(f"email:{email}")
        for phone in phones:
            generic_contacts.append(f"phone:{phone}")
        for number in whatsapp:
            generic_contacts.append(f"whatsapp:{number}")
        return {"emails": emails, "generic_emails": generic_emails, "phones": phones, "whatsapp": whatsapp, "all": generic_contacts}

    def _extract_whatsapp(self, text: str) -> list[str]:
        numbers = {f"+{match}" for match in WA_ME_PATTERN.findall(text)}
        numbers.update({f"+{match}" for match in WA_API_PATTERN.findall(text)})
        for match in re.finditer(r"WhatsApp", text, re.I):
            window = text[max(0, match.start() - PHONE_NEAR_WA_WINDOW): match.end() + PHONE_NEAR_WA_WINDOW]
            for phone in PHONE_PATTERN.findall(window):
                normalized = self._normalize_phone(phone)
                if normalized:
                    numbers.add(normalized)
        return sorted(numbers)

    def _normalize_phone(self, value: str) -> str | None:
        digits = re.sub(r"\D", "", value)
        if len(digits) < 10:
            return None
        return f"+{digits}"
