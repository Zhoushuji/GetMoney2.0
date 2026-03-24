import asyncio
import logging
from dataclasses import dataclass

from app.services.contact.intelligence import ContactIntelligenceService

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    core_contacts: list
    potential_contacts: list[dict]
    errors: list[str]


class ContactPipeline:
    """Run core-contact and potential-contact extraction in parallel."""

    def __init__(self) -> None:
        self.intelligence = ContactIntelligenceService()

    async def run(self, lead) -> PipelineResult:
        core_task = asyncio.create_task(self._find_core_contacts(lead))
        potential_task = asyncio.create_task(self._find_potential_contacts(lead))

        core_contacts, potential_contacts = await asyncio.gather(core_task, potential_task, return_exceptions=True)
        errors: list[str] = []

        if isinstance(core_contacts, Exception):
            errors.append(f"core_contacts:{type(core_contacts).__name__}:{core_contacts}")
            logger.exception(
                "contact_pipeline_core_failed lead_id=%s website=%s exception_type=%s exception_message=%s",
                getattr(lead, "id", None),
                getattr(lead, "website", None),
                type(core_contacts).__name__,
                str(core_contacts),
                exc_info=core_contacts,
            )

        if isinstance(potential_contacts, Exception):
            errors.append(f"potential_contacts:{type(potential_contacts).__name__}:{potential_contacts}")
            logger.exception(
                "contact_pipeline_potential_failed lead_id=%s website=%s exception_type=%s exception_message=%s",
                getattr(lead, "id", None),
                getattr(lead, "website", None),
                type(potential_contacts).__name__,
                str(potential_contacts),
                exc_info=potential_contacts,
            )

        return PipelineResult(
            core_contacts=core_contacts if not isinstance(core_contacts, Exception) else [],
            potential_contacts=potential_contacts if not isinstance(potential_contacts, Exception) else [],
            errors=errors,
        )

    async def _find_core_contacts(self, lead) -> list:
        return await self.intelligence.find_contacts(lead)

    async def _find_potential_contacts(self, lead) -> list[dict]:
        try:
            async with asyncio.timeout(15):
                pages = await self.intelligence._fetch_site_pages(lead.website)
                if not pages:
                    return []
                aggregated: list[dict] = []
                seen: set[tuple[str, str]] = set()
                for page_url, html in pages:
                    soup = self.intelligence._soup_from_html(html)
                    potentials = self.intelligence._extract_potential_contacts(lead.website, soup)
                    for key, values in potentials.items():
                        if key == "all":
                            continue
                        for value in values:
                            token = (key, value)
                            if token in seen:
                                continue
                            seen.add(token)
                            aggregated.append({"type": key, "value": value, "source_url": page_url})
                return aggregated
        except asyncio.TimeoutError:
            return []
