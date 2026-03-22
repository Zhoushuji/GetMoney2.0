class ProxyRotator:
    def pick(self, proxies: list[dict]) -> dict | None:
        active = [proxy for proxy in proxies if proxy.get("is_active", True)]
        return sorted(active, key=lambda item: item.get("score", 0), reverse=True)[0] if active else None
