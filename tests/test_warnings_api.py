"""Tests for P1-5: GET /warnings and PATCH /warnings/{id}/resolve endpoints."""
import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
import pytest_asyncio
import app.core.license_gate as _lg
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text


TEST_WARNING_AGENT_ID = uuid.UUID("c1111111-1111-1111-1111-111111111111")
TEST_WARNING_POLICY_ID = uuid.UUID("c2222222-2222-2222-2222-222222222222")


@contextmanager
def _mock_admin():
    from app.main import app
    from app.core.auth import require_admin
    app.dependency_overrides[require_admin] = lambda: {"role": "admin"}
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_admin, None)


@contextmanager
def _with_license():
    """Set enterprise license key so the gate passes for functional/auth tests."""
    with patch.object(_lg.settings, "AICONTROL_LICENSE_KEY", "test-key"):
        yield


@pytest_asyncio.fixture(scope="session")
async def p1_5_seed():
    """Insert a test agent and policy for warning FK constraints."""
    from app.models.database import async_session_factory

    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools)
            VALUES (:id, 'p1-5-test-agent', 'test@test.com', 'active', '[]'::jsonb)
            ON CONFLICT (id) DO NOTHING
        """), {"id": str(TEST_WARNING_AGENT_ID)})
        await session.commit()

    yield

    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM policy_warnings WHERE agent_id = :id OR tool_name LIKE 'p15_%'"),
            {"id": str(TEST_WARNING_AGENT_ID)},
        )
        await session.execute(
            text("DELETE FROM agents WHERE id = :id"),
            {"id": str(TEST_WARNING_AGENT_ID)},
        )
        await session.commit()


@pytest_asyncio.fixture(scope="session")
async def seed_warning(p1_5_seed):
    """Insert one active PolicyWarning and return its id."""
    from app.models.database import async_session_factory
    from app.models.policy_warning import PolicyWarning

    async with async_session_factory() as session:
        w = PolicyWarning(
            warning_type="UNGOVERNED_TOOL",
            agent_id=TEST_WARNING_AGENT_ID,
            policy_id=None,
            tool_name="p15_test_tool",
            message="Test warning for p1-5",
            is_active=True,
        )
        session.add(w)
        await session.commit()
        await session.refresh(w)
        warning_id = w.id

    yield str(warning_id)

    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM policy_warnings WHERE id = :id"),
            {"id": str(warning_id)},
        )
        await session.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_warnings_returns_list(p1_5_seed):
    """GET /warnings returns a list (may be empty)."""
    from app.main import app

    with _with_license(), _mock_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/warnings")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_warnings_filter_by_active(p1_5_seed, seed_warning):
    """GET /warnings?is_active=true returns only active warnings."""
    from app.main import app

    with _with_license(), _mock_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/warnings?is_active=true")

    assert response.status_code == 200
    for w in response.json():
        assert w["is_active"] is True


@pytest.mark.asyncio
async def test_get_warnings_requires_auth(p1_5_seed):
    """GET /warnings without auth returns 401 (enterprise license present)."""
    from app.main import app

    with _with_license():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/warnings")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_patch_warning_resolve(p1_5_seed, seed_warning):
    """PATCH /warnings/{id}/resolve marks warning as resolved."""
    from app.main import app

    with _with_license(), _mock_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(f"/warnings/{seed_warning}/resolve")

    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is False
    assert data["resolved_at"] is not None


@pytest.mark.asyncio
async def test_patch_warning_resolve_not_found(p1_5_seed):
    """PATCH /warnings/{non-existent-id}/resolve returns 404."""
    from app.main import app

    with _with_license(), _mock_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(f"/warnings/{uuid.uuid4()}/resolve")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_warning_resolve_requires_auth(p1_5_seed, seed_warning):
    """PATCH /warnings/{id}/resolve without auth returns 401 (enterprise license present)."""
    from app.main import app

    with _with_license():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(f"/warnings/{seed_warning}/resolve")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_warnings_requires_enterprise_license():
    """GET /warnings returns 402 without enterprise license."""
    from app.main import app

    with patch.object(_lg.settings, "AICONTROL_LICENSE_KEY", ""):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/warnings")

    assert response.status_code == 402
    assert response.json()["detail"]["error"] == "enterprise_license_required"


@pytest.mark.asyncio
async def test_warnings_resolve_requires_enterprise_license():
    """PATCH /warnings/{id}/resolve returns 402 without enterprise license."""
    from app.main import app

    with patch.object(_lg.settings, "AICONTROL_LICENSE_KEY", ""):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(f"/warnings/{uuid.uuid4()}/resolve")

    assert response.status_code == 402
    assert response.json()["detail"]["error"] == "enterprise_license_required"
