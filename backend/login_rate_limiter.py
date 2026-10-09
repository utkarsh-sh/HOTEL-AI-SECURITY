from collections import OrderedDict, deque
from threading import Lock
from time import monotonic


class LoginRateLimiter:
    """Thread-safe, bounded sliding-window limiter for login failures."""

    def __init__(
        self,
        max_failures: int = 5,
        window_seconds: float = 60.0,
        max_clients: int = 10_000,
        clock=monotonic,
    ):
        if max_failures <= 0:
            raise ValueError("max_failures must be positive.")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive.")
        if max_clients <= 0:
            raise ValueError("max_clients must be positive.")

        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self._clock = clock
        self._failures = OrderedDict()
        self._lock = Lock()

    def _prune(self, now: float) -> None:
        expired_clients = []

        for client_id, timestamps in self._failures.items():
            while timestamps and now - timestamps[0] >= self.window_seconds:
                timestamps.popleft()

            if not timestamps:
                expired_clients.append(client_id)

        for client_id in expired_clients:
            self._failures.pop(client_id, None)

    def _enforce_client_bound(self) -> None:
        while len(self._failures) > self.max_clients:
            self._failures.popitem(last=False)

    def check(self, client_id: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = self._clock()

        with self._lock:
            self._prune(now)

            timestamps = self._failures.get(client_id)
            if not timestamps or len(timestamps) < self.max_failures:
                return True, 0

            retry_after = max(
                1,
                int(self.window_seconds - (now - timestamps[0]) + 0.999),
            )
            return False, retry_after

    def record_failure(self, client_id: str) -> tuple[bool, int]:
        """Record a failed attempt and return its current allowance."""
        now = self._clock()

        with self._lock:
            self._prune(now)

            timestamps = self._failures.setdefault(client_id, deque())
            timestamps.append(now)

            self._failures.move_to_end(client_id)
            self._enforce_client_bound()

            if len(timestamps) < self.max_failures:
                return True, 0

            retry_after = max(
                1,
                int(self.window_seconds - (now - timestamps[0]) + 0.999),
            )
            return False, retry_after

    def clear(self, client_id: str) -> None:
        """Clear failures after successful authentication."""
        with self._lock:
            self._failures.pop(client_id, None)

    def client_count(self) -> int:
        """Return the number of currently tracked clients."""
        now = self._clock()

        with self._lock:
            self._prune(now)
            return len(self._failures)
