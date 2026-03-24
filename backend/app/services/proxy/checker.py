from dataclasses import dataclass


@dataclass
class ProxyHealth:
    latency_ms: float
    success: bool
    anonymity: str


async def check_proxy(proxy: dict) -> ProxyHealth:
    return ProxyHealth(latency_ms=120.0, success=True, anonymity="elite")
