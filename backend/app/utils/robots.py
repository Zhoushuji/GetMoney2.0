from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx


class RobotsChecker:
    API_ONLY_DOMAINS = {"linkedin.com", "facebook.com", "instagram.com"}

    def __init__(self) -> None:
        self._cache: dict[str, RobotFileParser] = {}

    async def is_allowed(self, url: str, user_agent: str = "LeadGenBot/1.0") -> bool:
        domain = urlparse(url).netloc.replace("www.", "")
        if domain in self.API_ONLY_DOMAINS:
            return True
        parser = await self._get_parser(domain)
        return parser.can_fetch(user_agent, url)

    async def _get_parser(self, domain: str) -> RobotFileParser:
        if domain in self._cache:
            return self._cache[domain]
        parser = RobotFileParser()
        robots_url = f"https://{domain}/robots.txt"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                else:
                    parser.parse([])
        except httpx.HTTPError:
            parser.parse([])
        self._cache[domain] = parser
        return parser
