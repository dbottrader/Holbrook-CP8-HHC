"""In-process sliding-window counters.

One coordinator process is the supported deployment. The window lives in
memory so a restart clears it; bans live in the database.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self.clock = clock or time.monotonic
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_sec: float) -> tuple[bool, int]:
        """Return (allowed, remaining). A rejected call still occupies the window."""
        if limit <= 0:
            return False, 0
        now = self.clock()
        bucket = self._events[key]
        while bucket and now - bucket[0] >= window_sec:
            bucket.popleft()
        if len(bucket) >= limit:
            return False, 0
        bucket.append(now)
        return True, limit - len(bucket)

    def reset(self) -> None:
        self._events.clear()
