"""Unit tests for the in-process auth rate limiter."""
import pytest
from fastapi import HTTPException

from app.core.rate_limiter import check_rate_limit, reset_rate_limits


@pytest.fixture(autouse=True)
def _clear():
    reset_rate_limits()
    yield
    reset_rate_limits()


def test_allows_up_to_max_attempts():
    for _ in range(5):
        check_rate_limit("k1", max_attempts=5, window_seconds=60)


def test_rejects_after_max_attempts():
    for _ in range(5):
        check_rate_limit("k2", max_attempts=5, window_seconds=60)
    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit("k2", max_attempts=5, window_seconds=60)
    assert exc_info.value.status_code == 429


def test_keys_are_independent():
    for _ in range(5):
        check_rate_limit("k3a", max_attempts=5, window_seconds=60)
    # A different key must not be affected by k3a's exhausted budget.
    check_rate_limit("k3b", max_attempts=5, window_seconds=60)


def test_old_attempts_expire_out_of_window(monkeypatch):
    import app.core.rate_limiter as rl

    t = [1000.0]
    monkeypatch.setattr(rl.time, "monotonic", lambda: t[0])

    for _ in range(5):
        check_rate_limit("k4", max_attempts=5, window_seconds=10)

    t[0] += 11  # past the window
    check_rate_limit("k4", max_attempts=5, window_seconds=10)  # must not raise
