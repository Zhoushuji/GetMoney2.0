import re
from dataclasses import dataclass

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



class ContactIntelligenceService:
    def __init__(self) -> None:
        self.classifier = TitleClassifier()

    def _soup_from_html(self, html: str):
        return BeautifulSoup(html, "html.parser")

    async def find_contacts(self, lead) -> list[ContactRead]:
        html = await self._fetch_html(lead.website)
        soup = self._soup_from_html(html) if html else None
        company_name = lead.company_name or ""

        linkedin_people = self._extract_linkedin_people(soup, company_name)
        verified_people = self._verify_people(linkedin_people, company_name)
        contact = self._build_contact(lead, verified_people, soup)
        return [contact] if contact else []

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

    def _build_contact(self, lead, verified_people: list[dict], soup: BeautifulSoup | None) -> ContactRead | None:
        potential_contacts = self._extract_potential_contacts(lead.website, soup)
        chosen = verified_people[0] if verified_people else None

        personal_email = None
        work_email = None
        phone = None
        whatsapp = potential_contacts.get("whatsapp", [None])[0]
        if chosen:
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

        if chosen is None and not any(potential_contacts.values()):
            return None

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
            potential_contacts={"items": potential_contacts.get("all", [])} if potential_contacts.get("all") else None,
            source_urls=[lead.website] if lead.website else [],
            verified_at=None,
        )

    def _extract_potential_contacts(self, website: str | None, soup: BeautifulSoup | None) -> dict[str, list[str]]:
        if soup is None:
            return {"emails": [], "phones": [], "whatsapp": [], "all": []}
        text = soup.get_text(" ", strip=True)
        hrefs = "\n".join(anchor.get("href") or "" for anchor in soup.select("a[href]"))
        emails = sorted({email for email in EMAIL_PATTERN.findall(text)})
        phones = sorted({self._normalize_phone(phone) for phone in PHONE_PATTERN.findall(text) if self._normalize_phone(phone)})
        whatsapp = self._extract_whatsapp(text + "\n" + hrefs)
        generic_contacts = []
        for email in emails:
            generic_contacts.append(f"email:{email}")
        for phone in phones:
            generic_contacts.append(f"phone:{phone}")
        for number in whatsapp:
            generic_contacts.append(f"whatsapp:{number}")
        return {"emails": emails, "phones": phones, "whatsapp": whatsapp, "all": generic_contacts}

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
