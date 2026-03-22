class LinkedInSearchService:
    async def search_company_pages(self, query: str) -> list[dict]:
        return [{"provider": "linkedin", "query": query, "note": "Playwright workflow placeholder"}]
