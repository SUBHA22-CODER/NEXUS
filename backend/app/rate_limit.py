"""Small in-process rate limiter for credential endpoints.

Single-process, best-effort protection. A multi-worker deployment should put a
shared limiter (gateway / Redis) in front instead; this one is deliberately
dependency-free and disabled in the test environment.
"""
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, status

from .config import get_settings


class SlidingWindowLimiter:
    """Rejects a key once it exceeds `max_hits` within `window_seconds`."""

    def __init__(self, max_hits: int, window_seconds: float) -> None:
        self.max_hits = max_hits
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and q[0] <= now - self.window:
            q.popleft()
        if len(q) >= self.max_hits:
            return False
        q.append(now)
        return True

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._hits.clear()
        else:
            self._hits.pop(key, None)


@dataclass(frozen=True)
class Limiter:
    limiter: SlidingWindowLimiter
    scope: str  # human label used in the 429 message


# Login is keyed per (ip, email) so one account can be protected while other
# accounts on the same IP keep working; register is keyed per IP to bound mass
# tenant creation.
LOGIN = Limiter(SlidingWindowLimiter(10, 60), "login")
REGISTER = Limiter(SlidingWindowLimiter(5, 60), "registration")


def gate(limiter: Limiter, key: str) -> None:
    if get_settings().env == "test":
        return
    if not limiter.limiter.allow(key):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many {limiter.scope} attempts. Try again in a minute.",
            headers={"Retry-After": "60"},
        )
