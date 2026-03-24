import httpx

from app.config import get_settings


class SerperClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def search(self, query: str, gl: str = "us", hl: str = "en", num: int = 10, page: int = 1) -> dict:
        if not self.settings.serper_api_key:
            return {"organic": [], "query": query, "provider": "serper", "stub": True, "page": page}

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": self.settings.serper_api_key, "Content-Type": "application/json"},
                json={"q": query, "gl": gl, "hl": hl, "num": num, "page": page},
            )
            response.raise_for_status()
            return response.json()


async def call_serper(query: str, gl: str = "us", hl: str = "en", num: int = 10, page: int = 1) -> dict:
    client = SerperClient()
    return await client.search(query=query, gl=gl, hl=hl, num=num, page=page)
