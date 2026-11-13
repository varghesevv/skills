"""A per-key limit on how often something may be asked, for endpoints open to everyone.

Kept in this process's memory, which is enough for one API instance; with several instances each
allows its own share (see docs/specification/09-infrastructure.md). Requests run in a thread
pool, so the check is guarded by a lock.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from app.core.errors import ApiError


class SlidingWindowLimiter:
    """At most `limit` calls per key within `window_seconds`."""

    # Above this many keys the idle ones are dropped, so the memory stays bounded.
    SWEEP_ABOVE = 1000

    def __init__(
        self,
        window_seconds: float,
        *,
        code: str = "rate_limited",
        message: str = "Too many requests. Try again later.",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._window = window_seconds
        self._code = code
        self._message = message
        self._clock = clock
        self._lock = threading.Lock()
        self._seen: dict[str, deque[float]] = {}

    def check(self, key: str, limit: int) -> None:
        with self._lock:
            now = self._clock()
            if len(self._seen) > self.SWEEP_ABOVE:
                self._sweep(now)
            times = self._seen.setdefault(key, deque())
            self._prune(times, now)
            if len(times) >= limit:
                wait = math.ceil(self._window - (now - times[0]))
                raise ApiError(
                    429, self._code, self._message, headers={"Retry-After": str(max(wait, 1))}
                )
            times.append(now)

    def _prune(self, times: deque[float], now: float) -> None:
        while times and now - times[0] >= self._window:
            times.popleft()

    def _sweep(self, now: float) -> None:
        for key in list(self._seen):
            self._prune(self._seen[key], now)
            if not self._seen[key]:
                del self._seen[key]

    def reset(self) -> None:
        with self._lock:
            self._seen.clear()


# One limiter per kind of open endpoint, each counted per client address. The limits are settings
# (SIGNUP_MAX_PER_HOUR, LINK_LOOKUP_MAX_PER_HOUR).
signup_limiter = SlidingWindowLimiter(
    3600, code="rate_limited", message="Too many sign-ups from this address. Try again later."
)
link_lookup_limiter = SlidingWindowLimiter(
    3600, code="rate_limited", message="Too many requests. Try again later."
)
# Vouching has its own count, so opening a link and then vouching is not two lookups.
vouch_attempt_limiter = SlidingWindowLimiter(
    3600, code="rate_limited", message="Too many requests. Try again later."
)
