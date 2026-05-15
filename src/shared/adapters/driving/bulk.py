"""Cross-cutting decorators for bulk admin routes.

Two concerns layered on top of every `/admin/.../bulk/...` route:

1. `bulk_action_log` — structured INFO log emission on logger
   `api.bulk` with counts only (never payload contents).
2. `bulk_rate_limited` — in-memory per-actor + per-action token-bucket
   limiter, gated by `app.config["BULK_RATE_LIMIT_ENABLED"]`.

The in-memory bucket is per-process and is NOT safe across gunicorn
workers; a production deployment that wants strict global limits
needs Redis-backed buckets. The stub is intentional — it gives flow
tests deterministic 429 behaviour without standing up Redis.
"""
from __future__ import annotations

import logging
import threading
import time
from functools import wraps
from typing import Any, Callable

from flask import current_app, make_response, request

from shared.adapters.driving.error_handlers import json_error_response

logger = logging.getLogger("api.bulk")

# Per-process in-memory state. Keyed by (actor_id, action) -> list[float].
# Not safe across gunicorn workers; see module docstring.
_BUCKETS: dict[tuple[Any, str], list[float]] = {}
_BUCKETS_LOCK = threading.Lock()

_VALID_MODES = {"ids", "filter"}
_WINDOW_SECONDS = 60.0


def reset_bulk_rate_limit_state() -> None:
    """Clear all in-memory bucket state. Exported for tests."""
    with _BUCKETS_LOCK:
        _BUCKETS.clear()


def _request_mode() -> str:
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return "unknown"
    target = body.get("target") or {}
    if not isinstance(target, dict):
        return "unknown"
    kind = target.get("kind")
    if kind in _VALID_MODES:
        return kind
    return "unknown"


def _actor_id() -> Any:
    payload = getattr(request, "admin_payload", None) or {}
    if not isinstance(payload, dict):
        return None
    return payload.get("sub")


def _extract_counts(response) -> tuple[int, int, int]:
    """Pull (total, ok, failed_count) from a Flask response.

    Falls back to all zeros when the body is not JSON or lacks the
    expected keys (e.g. rendered HTML partials).
    """
    try:
        body = response.get_json(silent=True)
    except Exception:  # noqa: BLE001 — never let logging break the response
        return 0, 0, 0
    if not isinstance(body, dict):
        return 0, 0, 0
    total = body.get("total") or 0
    ok = body.get("ok") or 0
    failed = body.get("failed")
    failed_count = len(failed) if isinstance(failed, list) else 0
    try:
        return int(total), int(ok), int(failed_count)
    except (TypeError, ValueError):
        return 0, 0, 0


def bulk_action_log(action: str) -> Callable:
    """Decorator: emit one INFO record on logger `api.bulk` per request.

    The record carries counts only — never the inbound payload. On
    exception, the record is emitted with all zeros and the exception
    re-raised so global handlers can map it to an HTTP response.
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            mode = _request_mode()
            actor_id = _actor_id()
            try:
                result = f(*args, **kwargs)
            except Exception:
                logger.info(
                    "bulk_action",
                    extra={
                        "event": "bulk action",
                        "action": action,
                        "mode": mode,
                        "total": 0,
                        "ok": 0,
                        "failed_count": 0,
                        "actor_id": actor_id,
                    },
                )
                raise

            response = make_response(result)
            total, ok, failed_count = _extract_counts(response)
            logger.info(
                "bulk_action",
                extra={
                    "event": "bulk action",
                    "action": action,
                    "mode": mode,
                    "total": total,
                    "ok": ok,
                    "failed_count": failed_count,
                    "actor_id": actor_id,
                },
            )
            return response

        return decorated

    return decorator


def bulk_rate_limited(action: str, *, max_per_min: int = 10) -> Callable:
    """Decorator: per-(actor, action) token bucket.

    Disabled by default; activated via `app.config["BULK_RATE_LIMIT_ENABLED"] = True`.
    On overflow returns 429 with a stable machine-readable code
    `RATE_LIMITED` — does NOT use `flask.abort(429)`, which would lose
    the code in the global HTTP handler.
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            enabled = bool(current_app.config.get("BULK_RATE_LIMIT_ENABLED", False))
            if not enabled:
                return f(*args, **kwargs)

            actor_id = _actor_id()
            # Unauthenticated/malformed-JWT traffic should never reach the
            # rate-limit step (permission_required is outer and blocks first),
            # but defend against a misconfigured wiring: pass through rather
            # than amplify a shared (None, action) bucket against legit users.
            if actor_id is None:
                return f(*args, **kwargs)

            key = (actor_id, action)
            now = time.time()
            cutoff = now - _WINDOW_SECONDS

            with _BUCKETS_LOCK:
                bucket = _BUCKETS.setdefault(key, [])
                # Drop stale timestamps
                fresh = [ts for ts in bucket if ts > cutoff]
                if not fresh:
                    # Bucket is empty after pruning — delete it to keep
                    # _BUCKETS bounded over time (process-local stub state).
                    _BUCKETS.pop(key, None)
                    fresh.append(now)
                    _BUCKETS[key] = fresh
                    over_limit = False
                elif len(fresh) >= max_per_min:
                    _BUCKETS[key] = fresh
                    over_limit = True
                else:
                    fresh.append(now)
                    _BUCKETS[key] = fresh
                    over_limit = False

            if over_limit:
                return json_error_response(
                    code="RATE_LIMITED",
                    message="Слишком много запросов. Попробуйте через минуту.",
                    status=429,
                )

            return f(*args, **kwargs)

        return decorated

    return decorator


__all__ = [
    "bulk_action_log",
    "bulk_rate_limited",
    "reset_bulk_rate_limit_state",
]
