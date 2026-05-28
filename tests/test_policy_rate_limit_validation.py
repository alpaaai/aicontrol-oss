"""Tests for P1-2: rate_limit condition validation on policy create/update."""
import pytest
from contextlib import contextmanager
from httpx import AsyncClient, ASGITransport

VALID_RATE_LIMIT_POLICY = {
    "name": "test_rate_val_policy",
    "description": "test",
    "rule_type": "rate_limit",
    "condition": {
        "tools": ["query_credit_bureau"],
        "rate_limit": {"max_calls": 10, "window": "session"},
    },
    "action": "deny",
    "active": True,
    "severity": "high",
    "compliance_tags": [],
}


@contextmanager
def _mock_admin():
    from app.main import app
    from app.core.auth import require_admin
    app.dependency_overrides[require_admin] = lambda: {"role": "admin"}
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_valid_rate_limit_policy_accepted():
    from app.main import app

    with _mock_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/policies", json=VALID_RATE_LIMIT_POLICY)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_invalid_window_rejected():
    from app.main import app

    policy = {**VALID_RATE_LIMIT_POLICY, "name": "test_rate_val_bad_window", "condition": {
        "tools": ["query_credit_bureau"],
        "rate_limit": {"max_calls": 10, "window": "1year"},
    }}
    with _mock_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/policies", json=policy)
    assert resp.status_code == 422
    assert "window" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_zero_max_calls_rejected():
    from app.main import app

    policy = {**VALID_RATE_LIMIT_POLICY, "name": "test_rate_val_zero_max", "condition": {
        "tools": ["query_credit_bureau"],
        "rate_limit": {"max_calls": 0, "window": "session"},
    }}
    with _mock_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/policies", json=policy)
    assert resp.status_code == 422
    assert "max_calls" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_empty_tools_rejected():
    from app.main import app

    policy = {**VALID_RATE_LIMIT_POLICY, "name": "test_rate_val_empty_tools", "condition": {
        "tools": [],
        "rate_limit": {"max_calls": 10, "window": "session"},
    }}
    with _mock_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/policies", json=policy)
    assert resp.status_code == 422
    assert "tools" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_on_exceed_rejected():
    from app.main import app

    policy = {**VALID_RATE_LIMIT_POLICY, "name": "test_rate_val_bad_exceed", "condition": {
        "tools": ["query_credit_bureau"],
        "rate_limit": {"max_calls": 10, "window": "session", "on_exceed": "escalate"},
    }}
    with _mock_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/policies", json=policy)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_on_exceed_optional_defaults_accepted():
    """Policy without on_exceed key must be accepted (defaults to deny)."""
    from app.main import app

    with _mock_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/policies", json={**VALID_RATE_LIMIT_POLICY, "name": "test_rate_val_no_exceed"})
    assert resp.status_code == 201
