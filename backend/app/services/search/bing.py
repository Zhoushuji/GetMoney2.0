import httpx

from app.config import get_settings


class BingClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def search(self, query: str, market: str = "en-US", count: int = 10) -> dict:
        if not self.settings.bing_api_key:
            return {"webPages": {"value": []}, "query": query, "provider": "bing", "stub": True}

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.bing.microsoft.com/v7.0/search",
                headers={"Ocp-Apim-Subscription-Key": self.settings.bing_api_key},
                params={"q": query, "mkt": market, "count": count},
            )
            response.raise_for_status()
            return response.json()
