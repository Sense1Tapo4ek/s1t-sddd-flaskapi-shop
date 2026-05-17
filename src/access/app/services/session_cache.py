import time
from dataclasses import dataclass, field
from threading import Lock

_DEFAULT_TTL_SECONDS = 60


@dataclass(slots=True)
class SessionCache:
    _ttl_seconds: int = _DEFAULT_TTL_SECONDS
    _store: dict[tuple[str, int], tuple[int, float]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def get(self, account_type: str, sub: int) -> int | None:
        """Returns cached token_version if not expired; None otherwise."""
        with self._lock:
            entry = self._store.get((account_type, sub))
            if entry is None:
                return None
            version, expires_at = entry
            if time.monotonic() >= expires_at:
                del self._store[(account_type, sub)]
                return None
            return version

    def put(self, account_type: str, sub: int, version: int) -> None:
        """Store/refresh token_version with TTL."""
        with self._lock:
            self._store[(account_type, sub)] = (
                version,
                time.monotonic() + self._ttl_seconds,
            )

    def invalidate(self, account_type: str, sub: int) -> None:
        """Drop cached entry (called on password-events, logout)."""
        with self._lock:
            self._store.pop((account_type, sub), None)

    def clear(self) -> None:
        """For tests / reset on app restart."""
        with self._lock:
            self._store.clear()
