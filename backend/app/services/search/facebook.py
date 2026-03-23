class FacebookSearchService:
    async def search_public_pages(self, query: str) -> list[dict]:
        return [{"provider": "facebook", "query": query, "note": "Public page placeholder"}]
