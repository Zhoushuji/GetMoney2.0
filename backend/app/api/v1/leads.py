import asyncio
import csv
import math
from datetime import datetime, timezone
from io import BytesIO, StringIO
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Query
from fastapi.responses import Response, StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.config import get_settings
from app.schemas.contact import ContactRead
from app.schemas.lead import LeadListResponse, LeadRead, LeadSearchRequest
from app.schemas.task import TaskCreateResponse, TaskStatusResponse
from app.services.search.company_extractor import CompanyNameExtractor
from app.services.search.serper import SerperClient
from app.services.search.social_links import extract_facebook, extract_linkedin_company, scrape_social_from_website

router = APIRouter(prefix="/leads", tags=["leads"])

TASKS: dict[str, dict] = {}
LEADS: dict[str, list[LeadRead]] = {}
CONTACTS: dict[str, list[ContactRead]] = {}
IGNORED_HOSTS = {"example.com", "example.org", "example.net", "linkedin.com", "www.linkedin.com", "facebook.com", "www.facebook.com"}
QUERY_TEMPLATES = [
    "{product} supplier in {country}",
    "{product} manufacturer in {country}",
    "{product} factory in {country}",
    "{product} exporter in {country}",
    "{product} wholesaler in {country}",
    "{product} company in {country}",
]
LANGUAGE_TO_GL = {
    "en": "us",
    "zh": "cn",
    "hi": "in",
    "ar": "ae",
    "fr": "fr",
    "de": "de",
    "es": "es",
    "pt": "br",
}


class SearchRuntime:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.serper_client = SerperClient()
        self.name_extractor = CompanyNameExtractor()
        self.search_semaphore = asyncio.Semaphore(max(1, self.settings.max_concurrent_searches))
        self.scrape_semaphore = asyncio.Semaphore(max(1, self.settings.max_concurrent_scrapers))


async def _safe_serper_search(serper_client: SerperClient, query: str, hl: str, gl: str, num: int, page: int = 1) -> dict:
    try:
        return await serper_client.search(query=query, hl=hl, gl=gl, num=num, page=page)
    except Exception:
        return {"organic": []}


async def _fetch_homepage(website: str, timeout: float = 15.0) -> tuple[BeautifulSoup | None, str | None]:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(website, headers={"User-Agent": "Mozilla/5.0 LeadGenBot/1.0"})
            response.raise_for_status()
    except Exception:
        return None, None
    return BeautifulSoup(response.text, "html.parser"), response.text


def _build_queries(payload: LeadSearchRequest) -> list[dict[str, str]]:
    countries = payload.countries or [""]
    languages = payload.languages or ["en"]
    queries: list[dict[str, str]] = []
    for country in countries:
        for language in languages:
            gl = LANGUAGE_TO_GL.get(language, "us")
            for template in QUERY_TEMPLATES:
                queries.append({
                    "country": country,
                    "language": language,
                    "gl": gl,
                    "query": template.format(product=payload.product_name, country=country).strip(),
                })
    return queries


def _max_pages(target_count: int | None) -> int:
    if target_count is None:
        return 3
    return max(1, min(10, math.ceil(target_count / 50)))


async def _search_serper_paginated(runtime: SearchRuntime, query: str, gl: str, hl: str, max_pages: int) -> list[dict]:
    results: list[dict] = []
    async with runtime.search_semaphore:
        for page in range(1, max_pages + 1):
            data = await _safe_serper_search(runtime.serper_client, query=query, hl=hl, gl=gl, num=10, page=page)
            organic = data.get("organic", [])
            results.extend(organic)
            if len(organic) < 10:
                break
    return results


async def _search_social_via_google(runtime: SearchRuntime, company_name: str, domain: str) -> dict[str, str | None]:
    facebook_query = f'"{company_name}" "{domain}" site:facebook.com'
    linkedin_query = f'"{company_name}" "{domain}" site:linkedin.com/company'
    facebook_data, linkedin_data = await asyncio.gather(
        _safe_serper_search(runtime.serper_client, query=facebook_query, hl="en", gl="us", num=5),
        _safe_serper_search(runtime.serper_client, query=linkedin_query, hl="en", gl="us", num=5),
    )
    facebook_text = "\n".join(item.get("link", "") for item in facebook_data.get("organic", []))
    linkedin_text = "\n".join(item.get("link", "") for item in linkedin_data.get("organic", []))
    return {"facebook": extract_facebook(facebook_text), "linkedin": extract_linkedin_company(linkedin_text)}


async def _get_social_links(runtime: SearchRuntime, company_name: str, website: str, soup: BeautifulSoup | None) -> dict[str, str | None]:
    domain = urlparse(website).netloc.removeprefix("www.")
    google_links = await _search_social_via_google(runtime, company_name, domain)
    website_links = await scrape_social_from_website(website, soup)
    return {
        "facebook": google_links.get("facebook") or website_links.get("facebook"),
        "linkedin": google_links.get("linkedin") or website_links.get("linkedin"),
    }


async def _build_lead_item(runtime: SearchRuntime, payload: LeadSearchRequest, serper_item: dict, country: str) -> dict | None:
    url = serper_item.get("link")
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not host or host in IGNORED_HOSTS:
        return None
    website = f"{parsed.scheme or 'https'}://{host}"

    async with runtime.scrape_semaphore:
        soup, _html = await _fetch_homepage(website)

    async def fetch_about_soup(url: str, timeout: float = 5.0) -> BeautifulSoup | None:
        about_soup, _ = await _fetch_homepage(url, timeout=timeout)
        return about_soup

    extracted_name = await runtime.name_extractor.extract(serper_item, website, soup, fetch_page=fetch_about_soup)
    social_links = await _get_social_links(runtime, extracted_name.value, website, soup)
    return {
        "company_name": extracted_name.value,
        "website": website,
        "facebook_url": social_links.get("facebook"),
        "linkedin_url": social_links.get("linkedin"),
        "country": country,
        "continent": None,
        "source": "google",
        "contact_status": "pending",
        "contact_name": None,
        "contact_title": None,
        "linkedin_personal_url": None,
        "personal_email": None,
        "work_email": None,
        "phone": None,
        "whatsapp": None,
        "potential_contacts": None,
        "raw_data": {
            "search_title": serper_item.get("title"),
            "search_snippet": serper_item.get("snippet"),
            "name_source": extracted_name.source,
        },
    }


async def _fetch_search_results(payload: LeadSearchRequest) -> list[dict]:
    runtime = SearchRuntime()
    queries = _build_queries(payload)
    paged_results = await asyncio.gather(*[
        _search_serper_paginated(runtime, query=item["query"], gl=item["gl"], hl=item["language"], max_pages=_max_pages(payload.target_count))
        for item in queries
    ])

    collected: list[dict] = []
    seen_hosts: set[str] = set()
    max_results = payload.target_count or len(queries) * 30

    for query_info, search_results in zip(queries, paged_results, strict=False):
        for item in search_results:
            lead_item = await _build_lead_item(runtime, payload, item, query_info["country"])
            if not lead_item:
                continue
            host = urlparse(lead_item["website"]).netloc.lower()
            if host in seen_hosts:
                continue
            seen_hosts.add(host)
            collected.append(lead_item)
            if payload.target_count and len(collected) >= payload.target_count:
                return collected
            if len(collected) >= max_results:
                return collected
    return collected


def build_task_status(task: dict) -> TaskStatusResponse:
    now = datetime.now(timezone.utc)
    leads = LEADS.get(str(task["id"]), [])
    confirmed_done = sum(1 for lead in leads if lead.contact_status == "done")
    stopped_early = task["target_count"] is not None and confirmed_done >= task["target_count"]
    status = "stopped_early" if stopped_early else task["status"]
    progress = 100 if status in {"completed", "stopped_early"} else task["progress"]
    task.update({"status": status, "progress": progress, "stopped_early": stopped_early, "updated_at": now, "confirmed_leads": confirmed_done})
    return TaskStatusResponse(
        id=task["id"],
        status=status,
        progress=progress,
        total=task["total"],
        completed=task["completed"],
        confirmed_leads=confirmed_done,
        target_count=task["target_count"],
        stopped_early=stopped_early,
        estimated_remaining_seconds=0,
        results_url=f"/api/v1/leads?task_id={task['id']}",
        created_at=task["created_at"],
        updated_at=task["updated_at"],
    )


def _style_workbook(sheet) -> None:
    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True)
    center_alignment = Alignment(vertical="center", wrap_text=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_alignment
    widths = {"A": 24, "B": 30, "C": 26, "D": 28, "E": 18, "F": 16, "G": 22, "H": 22, "I": 24, "J": 28, "K": 20, "L": 20, "M": 30}
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)


@router.post("/search", response_model=TaskCreateResponse)
async def create_lead_search(payload: LeadSearchRequest) -> TaskCreateResponse:
    task_id = uuid4()
    now = datetime.now(timezone.utc)
    results = await _fetch_search_results(payload)
    confirmed_leads = len(results) if payload.target_count is None else min(len(results), payload.target_count)
    total = max(len(results), confirmed_leads)
    TASKS[str(task_id)] = {
        "id": task_id,
        "status": "completed",
        "progress": 100,
        "total": total,
        "completed": total,
        "confirmed_leads": confirmed_leads,
        "target_count": payload.target_count,
        "stopped_early": payload.target_count is not None and confirmed_leads >= payload.target_count,
        "created_at": now,
        "updated_at": now,
    }
    LEADS[str(task_id)] = [
        LeadRead(id=uuid4(), task_id=task_id, created_at=now, **item)
        for item in results[:confirmed_leads]
    ]
    return TaskCreateResponse(task_id=task_id)


@router.get("", response_model=LeadListResponse)
async def list_leads(task_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)) -> LeadListResponse:
    items = LEADS.get(str(task_id), [])
    start = (page - 1) * page_size
    end = start + page_size
    return LeadListResponse(items=items[start:end], total=len(items), page=page, page_size=page_size)


@router.get("/export")
async def export_leads(task_id: UUID, format: str = "xlsx", include_contacts: bool = False):
    leads = LEADS.get(str(task_id), [])
    headers = ["company_name", "website", "facebook_url", "linkedin_url", "country", "status", "name_source"]
    if include_contacts:
        headers += ["contact_name", "contact_title", "personal_email", "work_email", "phone", "whatsapp", "potential_contacts"]
    if format == "csv":
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        for lead in leads:
            row = [lead.company_name or "", lead.website or "", lead.facebook_url or "", lead.linkedin_url or "", lead.country or "", lead.contact_status, (lead.raw_data or {}).get("name_source", "")]
            if include_contacts:
                row += [lead.contact_name or "", lead.contact_title or "", lead.personal_email or "", lead.work_email or "", lead.phone or "", lead.whatsapp or "", "; ".join((lead.potential_contacts or {}).get("items", []))]
            writer.writerow(row)
        return Response(content=buffer.getvalue(), media_type="text/csv")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Lead Results"
    pretty_headers = ["Company Name", "Website", "Facebook URL", "LinkedIn URL", "Country", "Status", "Name Source"]
    if include_contacts:
        pretty_headers += ["Contact Name", "Contact Title", "Personal Email", "Work Email", "Phone", "WhatsApp", "Potential Contacts"]
    sheet.append(pretty_headers)
    for lead in leads:
        row = [lead.company_name, lead.website, lead.facebook_url, lead.linkedin_url, lead.country, lead.contact_status, (lead.raw_data or {}).get("name_source")]
        if include_contacts:
            row += [lead.contact_name, lead.contact_title, lead.personal_email, lead.work_email, lead.phone, lead.whatsapp, "\n".join((lead.potential_contacts or {}).get("items", []))]
        sheet.append(row)
    _style_workbook(sheet)
    data = BytesIO()
    workbook.save(data)
    data.seek(0)
    return StreamingResponse(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.delete("")
async def delete_leads(task_id: UUID) -> dict:
    TASKS.pop(str(task_id), None)
    LEADS.pop(str(task_id), None)
    return {"deleted": True}
