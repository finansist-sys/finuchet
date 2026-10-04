"""In-memory sliding-window rate limiter (single process deployment)."""

from __future__ import annotations

import time
from collections import deque


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float, max_keys: int = 100_000) -> None:
        self.limit = limit
        self.window = window_seconds
        self.max_keys = max_keys
        self._hits: dict[bytes | str, deque[float]] = {}

    def allow(self, key: bytes | str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        bucket = self._hits.get(key)
        if bucket is None:
            if len(self._hits) >= self.max_keys:
                self._evict(now)
            bucket = self._hits[key] = deque()
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        return True

    def _evict(self, now: float) -> None:
        stale = [k for k, b in self._hits.items() if not b or now - b[-1] > self.window]
        for k in stale:
            del self._hits[k]
        if len(self._hits) >= self.max_keys:
            self._hits.clear()
