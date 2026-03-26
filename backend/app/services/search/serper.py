import asyncio

import httpx

from app.config import get_settings

_SERPER_CACHE: dict[tuple[str, str, str, int, int], dict] = {}
_SERPER_INFLIGHT: dict[tuple[str, str, str, int, int], asyncio.Task] = {}


class SerperClient:
    _shared_http_client: httpx.AsyncClient | None = None

    def __init__(self) -> None:
        self.settings = get_settings()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._shared_http_client is None:
            self.__class__._shared_http_client = httpx.AsyncClient(timeout=15.0)
        return self._shared_http_client

    async def _search_uncached(self, query: str, gl: str, hl: str, num: int, page: int) -> dict:
        if not self.settings.serper_api_key:
            return {"organic": [], "query": query, "provider": "serper", "stub": True, "page": page}

        client = await self._get_client()
        response = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": self.settings.serper_api_key, "Content-Type": "application/json"},
            json={"q": query, "gl": gl, "hl": hl, "num": num, "page": page},
        )
        response.raise_for_status()
        return response.json()

    async def search(self, query: str, gl: str = "us", hl: str = "en", num: int = 10, page: int = 1) -> dict:
        cache_key = (query, gl, hl, num, page)
        cached = _SERPER_CACHE.get(cache_key)
        if cached is not None:
            return cached

        inflight = _SERPER_INFLIGHT.get(cache_key)
        if inflight is None:
            inflight = asyncio.create_task(self._search_uncached(query=query, gl=gl, hl=hl, num=num, page=page))
            _SERPER_INFLIGHT[cache_key] = inflight

        try:
            result = await inflight
            _SERPER_CACHE[cache_key] = result
            return result
        finally:
            _SERPER_INFLIGHT.pop(cache_key, None)


async def call_serper(query: str, gl: str = "us", hl: str = "en", num: int = 10, page: int = 1) -> dict:
    client = SerperClient()
    return await client.search(query=query, gl=gl, hl=hl, num=num, page=page)
