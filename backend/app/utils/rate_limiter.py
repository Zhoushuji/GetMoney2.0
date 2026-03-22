import asyncio
import random

from app.config import get_settings


class DomainRateLimiter:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._locks: dict[str, asyncio.Lock] = {}

    async def wait(self, domain: str) -> None:
        lock = self._locks.setdefault(domain, asyncio.Lock())
        async with lock:
            delay = random.uniform(self.settings.request_delay_min, self.settings.request_delay_max)
            await asyncio.sleep(delay)
