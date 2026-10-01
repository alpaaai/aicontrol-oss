"""In-process sliding-window rate limiter for public auth endpoints.

Single-instance in-memory implementation. If AIControl ever runs multiple
API replicas behind a load balancer, this must move to a shared store
(e.g. Redis) -- per-process counters can be bypassed by round-robining
across replicas.
"""
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request

_attempts: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def check_rate_limit(key: str, max_attempts: int, window_seconds: float) -> None:
    """Raise 429 if `key` has already hit `max_attempts` within `window_seconds`."""
    now = time.monotonic()
    with _lock:
        cutoff = now - window_seconds
        attempts = [t for t in _attempts[key] if t > cutoff]
        if len(attempts) >= max_attempts:
            _attempts[key] = attempts
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
        attempts.append(now)
        _attempts[key] = attempts


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def reset_rate_limits() -> None:
    """Test-only: clear all tracked attempts."""
    with _lock:
        _attempts.clear()
