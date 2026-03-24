import re
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from uuid import uuid4

from app.schemas.contact import ContactRead
from app.services.contact.classifier import TitleClassifier

PHONE_NEAR_WA_WINDOW = 50
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
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_PATTERN = re.compile(r"(?:\+\d[\d\s()-]{8,}\d)")
WA_ME_PATTERN = re.compile(r"wa\.me/(\d{10,15})", re.I)
WA_API_PATTERN = re.compile(r"api\.whatsapp\.com/send\?phone=(\d{10,15})", re.I)
CONTACT_SCAN_PATHS = ["/", "/about", "/about-us", "/team", "/leadership", "/contact", "/contact-us"]



class ContactIntelligenceService:
    def __init__(self) -> None:
        self.classifier = TitleClassifier()

    def _soup_from_html(self, html: str):
        return BeautifulSoup(html, "html.parser")

    async def find_contacts(self, lead) -> list[ContactRead]:
        return await self.find_decision_makers(lead)

    async def find_decision_makers(self, lead) -> list[ContactRead]:
        pages = await self._fetch_site_pages(lead.website)
        combined_html = "\n".join(html for _, html in pages)
        soup = self._soup_from_html(combined_html) if combined_html else None
        company_name = lead.company_name or ""
        source_urls = [url for url, _ in pages]
        potential_contacts = self._extract_potential_contacts(lead.website, soup)

        linkedin_people = self._extract_linkedin_people(soup, company_name)
        verified_people = self._verify_people(linkedin_people, company_name)
        contact = self._build_contact(lead, verified_people, potential_contacts, source_urls=source_urls)
        return [contact] if contact else []

    async def find_potential_contacts(self, lead) -> dict[str, list[str]]:
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
            candidates.append({"person_name": text or None, "title": title, "linkedin_personal_url": href})
        return candidates

    def _verify_people(self, people: list[dict], company_name: str) -> list[dict]:
        verified: list[dict] = []
        normalized_company = company_name.lower()
        for person in people:
            name = person.get("person_name") or ""
            title = person.get("title") or ""
            linkedin = person.get("linkedin_personal_url") or ""
            if any(pattern.search(name) for pattern in INVALID_PERSON_NAME_PATTERNS):
                continue
            if any(pattern.search(linkedin) for pattern in INVALID_LINKEDIN_PATTERNS):
                continue
            is_allowed, priority = self.classifier.classify(title)
            if not is_allowed:
                continue
            person["priority"] = priority
            # lightweight cross-validation inference: require at least one company token in nearby text/name/title payload
            tokens = [token for token in normalized_company.split() if len(token) > 2]
            if tokens and not any(token in f"{name} {title} {linkedin}".lower() for token in tokens):
                # inference fallback: still allow when linkedin path looks person-like and title is strong match
                if priority > 2:
                    continue
            verified.append(person)
        return sorted(verified, key=lambda item: item.get("priority") or 999)

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
            source_urls=source_urls or ([lead.website] if lead.website else []),
            verified_at=None,
        )

    def _extract_potential_contacts(self, website: str | None, soup: BeautifulSoup | None) -> dict[str, list[str]]:
        if soup is None:
            return {"emails": [], "phones": [], "whatsapp": [], "all": []}
        text = soup.get_text(" ", strip=True)
        hrefs = "\n".join(anchor.get("href") or "" for anchor in soup.select("a[href]"))
        emails = sorted({email for email in EMAIL_PATTERN.findall(text)})
        generic_emails = sorted([email for email in emails if any(pattern.search(email) for pattern in INVALID_EMAIL_AS_PERSONAL)])
        phones = sorted({self._normalize_phone(phone) for phone in PHONE_PATTERN.findall(text) if self._normalize_phone(phone)})
        whatsapp = self._extract_whatsapp(text + "\n" + hrefs)
        generic_contacts = []
        for email in emails:
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
