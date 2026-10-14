"""Bounded in-process sliding-window limiter for single-instance deployments."""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque


class SlidingWindowRateLimiter:
    def __init__(self, *, window_seconds: int = 60, max_keys: int = 10_000) -> None:
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._events: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str, *, limit: int, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        async with self._lock:
            events = self._events.get(key)
            if events is None:
                if len(self._events) >= self.max_keys:
                    self._prune_all(cutoff)
                if len(self._events) >= self.max_keys:
                    return False, self.window_seconds
                events = self._events[key] = deque()
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False, max(1, math.ceil(events[0] + self.window_seconds - current))
            events.append(current)
            return True, 0

    def _prune_all(self, cutoff: float) -> None:
        for key, events in tuple(self._events.items()):
            while events and events[0] <= cutoff:
                events.popleft()
            if not events:
                self._events.pop(key, None)
