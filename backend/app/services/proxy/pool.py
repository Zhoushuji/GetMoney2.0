from dataclasses import dataclass
from datetime import datetime, timezone

from app.services.proxy.checker import check_proxy
from app.services.proxy.rotator import ProxyRotator


@dataclass
class ProxyRecord:
    proxy_id: str
    country: str | None
    score: float
    url: str
    is_active: bool = True
    last_checked: datetime | None = None


class ProxyPool:
    SOURCES = ["env_static", "paid_api", "free_list"]
    SCORE_FACTORS = {"latency_ms": -0.3, "success_rate": 0.5, "anonymity": 0.2}

    def __init__(self, proxies: list[ProxyRecord] | None = None) -> None:
        self.proxies = proxies or []
        self.rotator = ProxyRotator()

    async def get_proxy(self, target_country: str | None = None) -> ProxyRecord | None:
        pool = [p for p in self.proxies if p.is_active and (not target_country or p.country == target_country)]
        selected = self.rotator.pick([proxy.__dict__ for proxy in pool])
        return next((proxy for proxy in pool if proxy.proxy_id == selected["proxy_id"]), None) if selected else None

    async def report_failure(self, proxy_id: str, reason: str) -> None:
        for proxy in self.proxies:
            if proxy.proxy_id == proxy_id:
                proxy.score = max(0.0, proxy.score - 0.2)
                proxy.is_active = proxy.score > 0.1
                return

    async def health_check_all(self) -> None:
        for proxy in self.proxies:
            health = await check_proxy(proxy.__dict__)
            proxy.last_checked = datetime.now(timezone.utc)
            proxy.score = max(0.0, proxy.score + (0.1 if health.success else -0.3))
