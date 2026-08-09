from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """Small zero-cost limiter for a single API process.

    Production deployments with multiple workers should replace this store with
    a shared backend at the edge or in Redis.
    """

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str, *, limit: int, period_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - period_seconds
        async with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait and try again.",
                )
            events.append(now)


limiter = InMemoryRateLimiter()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce_rate_limit(
    request: Request,
    scope: str,
    *,
    limit: int,
    period_seconds: int = 60,
    identity: str | None = None,
) -> None:
    await limiter.check(
        f"{scope}:ip:{client_ip(request)}",
        limit=limit,
        period_seconds=period_seconds,
    )
    if identity:
        await limiter.check(
            f"{scope}:identity:{identity.strip().lower()}",
            limit=limit,
            period_seconds=period_seconds,
        )
