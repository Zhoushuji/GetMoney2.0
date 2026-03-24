import asyncio
from dataclasses import dataclass

from app.services.contact.intelligence import ContactIntelligenceService


@dataclass
class PipelineResult:
    core_contacts: list
    potential_contacts: list[dict]


class ContactPipeline:
    """Run core-contact and potential-contact extraction in parallel."""

    def __init__(self) -> None:
        self.intelligence = ContactIntelligenceService()

    async def run(self, lead) -> PipelineResult:
        core_task = asyncio.create_task(self._find_core_contacts(lead))
        potential_task = asyncio.create_task(self._find_potential_contacts(lead))

        core_contacts, potential_contacts = await asyncio.gather(core_task, potential_task, return_exceptions=True)

        return PipelineResult(
            core_contacts=core_contacts if not isinstance(core_contacts, Exception) else [],
            potential_contacts=potential_contacts if not isinstance(potential_contacts, Exception) else [],
        )

    async def _find_core_contacts(self, lead) -> list:
        return await self.intelligence.find_contacts(lead)

    async def _find_potential_contacts(self, lead) -> list[dict]:
        try:
            async with asyncio.timeout(15):
                html = await self.intelligence._fetch_html(lead.website)
                if not html:
                    return []
                soup = self.intelligence._soup_from_html(html)
                potentials = self.intelligence._extract_potential_contacts(lead.website, soup)
                return [{"type": key, "value": value} for key, values in potentials.items() for value in values if key != "all"]
        except asyncio.TimeoutError:
            return []
