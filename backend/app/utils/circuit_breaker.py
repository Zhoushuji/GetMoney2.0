from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class CircuitBreaker:
    domain: str
    state: str = "CLOSED"
    failures: deque[datetime] = field(default_factory=deque)
    consecutive_failures: int = 0
    opened_at: datetime | None = None

    _registry: dict[str, "CircuitBreaker"] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def for_domain(cls, domain: str) -> "CircuitBreaker":
        if not hasattr(cls, "registry"):
            cls.registry = {}
        if domain not in cls.registry:
            cls.registry[domain] = cls(domain=domain)
        return cls.registry[domain]

    def record_success(self) -> None:
        self.state = "CLOSED"
        self.consecutive_failures = 0
        self.failures.clear()
        self.opened_at = None

    def record_failure(self) -> None:
        now = datetime.now(timezone.utc)
        self.failures.append(now)
        self.consecutive_failures += 1
        self._trim(now)
        if self.consecutive_failures >= 5 or self.failure_rate(now) > 0.5:
            self.state = "OPEN"
            self.opened_at = now

    def allow_request(self) -> bool:
        now = datetime.now(timezone.utc)
        if self.state == "OPEN" and self.opened_at and now - self.opened_at > timedelta(seconds=30):
            self.state = "HALF_OPEN"
            return True
        return self.state != "OPEN"

    def failure_rate(self, now: datetime) -> float:
        self._trim(now)
        window = [ts for ts in self.failures if now - ts <= timedelta(seconds=60)]
        return min(len(window) / 5, 1.0)

    def _trim(self, now: datetime) -> None:
        while self.failures and now - self.failures[0] > timedelta(seconds=60):
            self.failures.popleft()
